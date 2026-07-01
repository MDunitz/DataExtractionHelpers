# labdata

Shared, **config-free** Google-Sheets extraction + astropy-units round-trip for
the reproducible science work. Code only — no spreadsheet IDs, no credentials in the package
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

`auth=True` uses `google.auth.default()`, which reads
`GOOGLE_APPLICATION_CREDENTIALS`. Set it once in your shell profile so the same
service account works across every repo:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/keys/orphan-sheets-ro.json"
```

Share the target sheet with the service-account email (Viewer). Read-only scope.

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
