"""astropy-units round-trip between pandas DataFrames and ECSV.

Moved verbatim from saltyBiomass `experiments/processing/data_extraction.py`
(the unit-aware (de)serialization core), which had no repo coupling.
"""

import pandas as pd
from astropy import units as u
from astropy.table import Table
from astropy.time import Time
from astropy.units import cds


def _column_unit(series):
    """Return the unit of the first astropy Quantity in the column, or None if
    the column holds no Quantities. Scans the whole column so a leading null or
    leading bare value doesn't hide a units column."""
    for v in series:
        if hasattr(v, "unit"):
            return v.unit
    return None


def _quantity_column_to_values(series, unit, col):
    """Magnitudes of a units column, all converted to `unit`. Nulls become NaN.

    Differing prefixes (e.g. mol and mmol) are converted via Quantity.to() so
    the stored magnitudes are consistent. A non-null value with no unit means a
    unit went missing upstream; per the one-unit-per-column invariant that is a
    bug, so it raises (naming the column) rather than being silently mislabeled.
    Quantity.to() raises UnitConversionError for incompatible physical types.
    """
    values = []
    for v in series:
        if hasattr(v, "unit"):
            values.append(v.to(unit).value)
        elif pd.isna(v):
            values.append(float("nan"))
        else:
            raise ValueError(
                f"Column {col!r} has a unitless value {v!r} among {unit} "
                f"Quantities. Every value in a units column must carry the "
                f"same unit — a missing unit upstream is the likely cause."
            )
    return values


def to_table(df):
    """Convert a pandas DataFrame to an astropy Table, preserving units and
    datetimes."""
    t = Table()
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            t[col] = Time(series)
            continue
        unit = _column_unit(series)
        if unit is not None:
            t[col] = _quantity_column_to_values(series, unit, col)
            t[col].unit = unit
        else:
            t[col] = series.values
    return t


def to_pandas(t):
    """Convert an astropy Table back to a pandas DataFrame, restoring units."""
    df = pd.DataFrame()
    for col in t.colnames:
        if isinstance(t[col], Time):
            df[col] = pd.to_datetime(t[col].iso)
        elif hasattr(t[col], "unit") and t[col].unit is not None:
            unit = t[col].unit
            if isinstance(unit, u.UnrecognizedUnit) and str(unit) == "%":
                unit = u.percent
            df[col] = [val * unit for val in t[col].value]
        else:
            df[col] = t[col].data
    return df


def save_data_frame_with_units(df, file_path, verbose=False):
    """Save a DataFrame as .ecsv to preserve astropy units (use the .ecsv
    extension to retain unit metadata)."""
    table = to_table(df)
    table.write(file_path, overwrite=True)
    if verbose:
        print(f"File saved to: {file_path}")


def extract_data_frame_with_units(file_path):
    """Load a .ecsv file back into a pandas DataFrame with astropy units
    restored."""
    with cds.enable():
        t_loaded = Table.read(file_path)
    return to_pandas(t_loaded)
