"""Google-Sheets extraction: public CSV export + authenticated (gspread) path,
single-tab and whole-workbook, with a logical-name registry and local CSV cache.

Decoupled from any project layout (no PROJECT_ROOT): the cache directory is
resolved from an explicit arg, the LABDATA_CACHE_DIR env var, or CWD/.labdata_cache.

Compatibility contract (saltyBiomass call-site audit, claude_notes #340):
  - extract_google_sheet's first two params stay positional (spreadsheet_id,
    data_name); from_cache/cache/sheet_id keep names + order. New options
    (cache_dir, auth) are KEYWORD-ONLY (after *), so no positional caller breaks.
  - get_latest_filename(sheet_id, data_name) keeps the 2-positional form.
"""

import csv
import glob
import io
import logging
import os
import urllib.request

import pandas as pd

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_ENV = "LABDATA_CACHE_DIR"

# Name registry: logical name -> (spreadsheet_id, default_gid). Populated by the
# CONSUMER via register_sheet(); the public package ships no IDs (IDs identify
# but do not authorize, and live in consumers per #162).
_REGISTRY = {}


# --- cache dir + filenames --------------------------------------------------

def _resolve_cache_dir(cache_dir=None):
    """Precedence: explicit arg > LABDATA_CACHE_DIR env > CWD/.labdata_cache.
    saltyBiomass keeps its old cache by setting LABDATA_CACHE_DIR to
    $PROJECT_ROOT/data/local_data."""
    if cache_dir:
        return cache_dir
    return os.environ.get(_DEFAULT_CACHE_ENV,
                          os.path.join(os.getcwd(), ".labdata_cache"))


def get_latest_filename(sheet_id, data_name, *, cache_dir=None):
    """Newest cache filename for (data_name, sheet_id). Cache-name scheme is
    `name___epoch___id.csv` (load-bearing for the max-by-epoch pick).

    NB `sheet_id` here historically receives the *spreadsheet* id (saltyBiomass
    misnomer kept for call-site compatibility).

    Fixes two latent bugs from the saltyBiomass original (do not enshrine):
      (a) match BOTH data_name and id (the original matched id only);
      (b) `removesuffix('.csv')` instead of `.strip('.csv')` (which stripped a
          char set, not the suffix).
    """
    cache_dir = _resolve_cache_dir(cache_dir)
    files = glob.glob(os.path.join(cache_dir, "*.csv"))
    stems = [os.path.basename(f).removesuffix(".csv") for f in files]
    parts = [s.split("___") for s in stems if len(s.split("___")) > 2]
    times = [p[1] for p in parts if p[0] == data_name and p[2] == sheet_id]
    if not times:
        raise FileNotFoundError(
            f"no cache for data_name={data_name!r}, id={sheet_id!r} in {cache_dir}"
        )
    max_time = max(times, key=int)
    return f"{data_name}___{max_time}___{sheet_id}.csv"


# --- low-level fetch (the backend seam) -------------------------------------

def _csv_export_url(spreadsheet_id, sheet_id=0):
    base = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
    return base if not sheet_id else f"{base}&gid={sheet_id}"


def _xlsx_export_url(spreadsheet_id):
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"


def _fetch_bytes(url):
    """GET url -> bytes. Raises on an HTML response (Google's sign-in/permission
    wall), which bare pd.read_csv(url) would otherwise parse into garbage. Folded
    in from microbialCommunities loadcell_sheets (strict improvement: only the
    failure mode changes)."""
    req = urllib.request.Request(url, headers={"User-Agent": "labdata"})
    with urllib.request.urlopen(req) as resp:
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read()
    if "text/html" in ctype.lower():
        raise RuntimeError(
            "Got an HTML page, not a file. The sheet is probably not shared "
            "'anyone with the link can view'. Use auth=True (service account) "
            f"or share it. URL: {url}"
        )
    return body


def _values_to_df(rows, **kwargs):
    """2D worksheet values -> DataFrame via a CSV round-trip, so the same pandas
    `kwargs` (dtype, parse_dates, ...) apply identically to the public path."""
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    buf.seek(0)
    return pd.read_csv(buf, **kwargs)


def _gspread_client(auth):
    """gspread client (read-only). auth=str -> that key file; auth truthy ->
    Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS). Imports are
    local so the public path never requires gspread/google-auth."""
    import gspread
    readonly = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    if isinstance(auth, str):
        return gspread.service_account(filename=auth, scopes=readonly)
    import google.auth
    creds, _ = google.auth.default(scopes=readonly)
    return gspread.authorize(creds)


# --- single-tab extraction (id-based; back-compatible signature) ------------

def extract_google_sheet(spreadsheet_id, data_name, from_cache=True, cache=False,
                         sheet_id=0, *, cache_dir=None, auth=False, **kwargs):
    """Pull one worksheet into a DataFrame, with optional local CSV caching.

    auth: falsy -> public CSV export (sheet must be link-readable). True ->
      Sheets API via gspread + Application Default Credentials. str -> a specific
      service-account key file. `**kwargs` go to pandas read_csv in both paths.
    """
    if from_cache:
        try:
            filename = get_latest_filename(spreadsheet_id, data_name,
                                           cache_dir=cache_dir)
            file_path = os.path.join(_resolve_cache_dir(cache_dir), filename)
            df = pd.read_csv(file_path, **kwargs)
            logger.info("Loaded %s from cache: %s", data_name, file_path)
            return df
        except Exception:
            logger.info("No cache for %s; pulling from source", data_name)

    if auth:
        gc = _gspread_client(auth)
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.sheet1 if not sheet_id else sh.get_worksheet_by_id(int(sheet_id))
        df = _values_to_df(ws.get_all_values(), **kwargs)
        logger.info("Pulled %s via authenticated Sheets API (gid=%s)",
                    data_name, sheet_id)
    else:
        url = _csv_export_url(spreadsheet_id, sheet_id)
        df = _values_to_df(list(csv.reader(io.StringIO(
            _fetch_bytes(url).decode("utf-8")))), **kwargs)
        logger.info("Pulled %s from source: %s", data_name, url)

    if cache:
        import time
        filename = f"{data_name}___{int(time.time())}___{spreadsheet_id}.csv"
        cache_path = _resolve_cache_dir(cache_dir)
        os.makedirs(cache_path, exist_ok=True)
        file_path = os.path.join(cache_path, filename)
        df.to_csv(file_path)
        logger.info("Cached %s to: %s", data_name, file_path)
    return df


# --- whole-workbook / multi-tab (what loadcell needs) -----------------------

def read_workbook_tabs(spreadsheet_id, tab_filter=None, *, cache_dir=None,
                       auth=False):
    """Fetch the whole workbook; return {tab_name: DataFrame}.

    tab_filter: optional predicate(tab_name)->bool (loadcell passes the
    data_YYYY-MM regex match). Public path pulls the .xlsx export; auth path
    iterates worksheets via gspread.
    """
    if auth:
        gc = _gspread_client(auth)
        sh = gc.open_by_key(spreadsheet_id)
        out = {}
        for ws in sh.worksheets():
            if tab_filter and not tab_filter(ws.title):
                continue
            out[ws.title] = _values_to_df(ws.get_all_values())
        return out

    book = pd.read_excel(io.BytesIO(_fetch_bytes(_xlsx_export_url(spreadsheet_id))),
                         sheet_name=None)
    return {name: df for name, df in book.items()
            if (tab_filter is None or tab_filter(name))}


# --- logical-name registry (de-hardcode IDs) --------------------------------

def register_sheet(name, spreadsheet_id, gid=0):
    """Map a logical name -> (spreadsheet_id, default gid). Consumers call this
    once (e.g. in a sheets_config.py); the public package ships no IDs."""
    _REGISTRY[name] = (spreadsheet_id, gid)


def resolve_sheet(name):
    if name not in _REGISTRY:
        raise KeyError(f"unknown sheet {name!r}; register_sheet() it first")
    return _REGISTRY[name]


def extract(name, *, from_cache=True, cache=False, gid=None, cache_dir=None,
            auth=False, **kwargs):
    """Name-based entry point: resolve name -> (id, gid), then fetch. A per-call
    `gid=` overrides the registered default."""
    spreadsheet_id, default_gid = resolve_sheet(name)
    return extract_google_sheet(
        spreadsheet_id, name, from_cache=from_cache, cache=cache,
        sheet_id=(default_gid if gid is None else gid),
        cache_dir=cache_dir, auth=auth, **kwargs)
