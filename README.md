# labdata

Shared, **config-free** Google-Sheets extraction + astropy-units round-trip for
the Orphan lab. Code only — no spreadsheet IDs, no credentials in the package
(those live in the consumer). Implements the design in
the design in claude_notes #340 / microbialCommunities #162.

## Install (from Git)

Self-contained package directory; install straight from the repo:

```bash
pip install "git+https://github.com/MDunitz/DataExtractionHelpers.git"
# auth (private sheets) extra:
pip install "labdata[auth] @ git+https://github.com/MDunitz/DataExtractionHelpers.git"
```

## Quickstart

```python
from labdata import register_sheet, extract

# one-time, in the consumer (e.g. a sheets_config.py) — IDs live here, not in labdata
register_sheet("pressure_data", "1AbC...xyz", gid=0)

df = extract("pressure_data")                 # public, cached
df = extract("pressure_data", from_cache=False, cache=True)   # refresh + cache
```

Lower-level, id-based (back-compatible with saltyBiomass call sites):

```python
from labdata import extract_google_sheet, read_workbook_tabs
df = extract_google_sheet(spreadsheet_id, "name", sheet_id=gid)

# whole workbook (what the load-cell dashboard needs):
import re
rx = re.compile(r"^data_\d{4}-\d{2}$")
tabs = read_workbook_tabs(spreadsheet_id, tab_filter=lambda n: bool(rx.match(n)))
```

## Private sheets (auth)

```python
extract("pressure_data", auth=True)            # Application Default Credentials
extract("pressure_data", auth="/path/key.json")  # specific service-account key
```

`auth=True` uses `google.auth.default()` (Application Default Credentials),
which resolve to **either** a service-account key file (via
`GOOGLE_APPLICATION_CREDENTIALS`) **or** user credentials from
`gcloud auth application-default login`. Pick one path below.

### First-time GCP setup

Both paths first need the Sheets API enabled in a project you can use (labdata
opens sheets by key via the Sheets API; the Drive API is not required):

```bash
gcloud config set project <PROJECT_ID>
gcloud services enable sheets.googleapis.com
```

#### Option A — user credentials, keyless (simplest for a personal laptop)

No key file to store or leak. Authenticates as *you*, so the sheet only needs to
be shared with your own Google account (usually already the case).

```bash
gcloud auth application-default login \
  --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets.readonly"
gcloud auth application-default set-quota-project <PROJECT_ID>
```

- The `spreadsheets.readonly` scope **must** be in the login command. User
  credentials cannot self-expand scopes at runtime, and labdata requests exactly
  that scope; a login without it fails the first time you call `auth=True`.
- The `set-quota-project` line is required — user credentials calling the Sheets
  API need a quota project, or calls fail with a quota-project error.
- **Do not** set `GOOGLE_APPLICATION_CREDENTIALS` for this path; if it is set,
  the key file takes precedence over your gcloud login.
- If the browser flow returns `Access blocked: Authorization Error`, your org
  disallows the default gcloud client for non-Cloud scopes — use Option B, or
  supply your own OAuth client id with `--client-id-file`.

#### Option B — service-account key file (headless / shared machines)

1. Create a service account (`IAM & Admin → Service Accounts → Create`). No
   project roles are needed — sheet access comes from *sharing the sheet*, not
   from IAM.
2. Create a JSON key (`Keys → Add key → JSON`) and download it.
3. Store it outside any repo and lock it down, then point ADC at it:
   ```bash
   mkdir -p ~/.config/gcloud/keys
   mv ~/Downloads/<key>.json ~/.config/gcloud/keys/orphan-sheets-ro.json
   chmod 600 ~/.config/gcloud/keys/orphan-sheets-ro.json
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/keys/orphan-sheets-ro.json"
   ```
   Put the `export` in your shell profile so the same key works across every repo.
4. Share the target sheet with the service-account email
   (`...@....iam.gserviceaccount.com`) as **Viewer**.

> **Org-policy gotcha:** many institutional GCP orgs enforce
> `iam.disableServiceAccountKeyCreation`, which blocks step 2 entirely. If key
> download is disabled, use Option A, or request a policy exception / use a
> project outside the org.

Either way the credential is read-only (`spreadsheets.readonly`); never commit a
key file.

## Cache directory

CSV cache location precedence: `cache_dir=` arg → `LABDATA_CACHE_DIR` env →
`./.labdata_cache`. saltyBiomass keeps its existing cache by setting
`LABDATA_CACHE_DIR=$PROJECT_ROOT/data/local_data`.

## Units round-trip

```python
from labdata import save_data_frame_with_units, extract_data_frame_with_units
save_data_frame_with_units(df, "out.ecsv")     # preserves astropy units + datetimes
df = extract_data_frame_with_units("out.ecsv")
```
