"""ECSV units round-trip — ported from saltyBiomass TestEcsvUnitRoundTrip."""

import os
import tempfile

import pandas as pd
from astropy import units as u

from labdata import (
    extract_data_frame_with_units,
    save_data_frame_with_units,
    to_pandas,
    to_table,
)


def _sample_df():
    return pd.DataFrame({
        "t": pd.to_datetime(["2026-06-01T00:00:00Z", "2026-06-01T01:00:00Z"]),
        "mass": [1.5 * u.g, 2.0 * u.g],
        "conc": [10.0 * u.mmol / u.L, 12.0 * u.mmol / u.L],
        "label": ["a", "b"],
    })


def test_ecsv_roundtrip_preserves_units_and_values(tmp_path=None):
    df = _sample_df()
    path = os.path.join(tempfile.mkdtemp(), "rt.ecsv")
    save_data_frame_with_units(df, path)
    out = extract_data_frame_with_units(path)

    assert list(out.columns) == list(df.columns)
    assert out["mass"][0].unit == u.g
    assert out["mass"][1].value == 2.0
    assert out["conc"][0].to(u.mmol / u.L).value == 10.0
    assert list(out["label"]) == ["a", "b"]
    assert pd.api.types.is_datetime64_any_dtype(out["t"])


def test_to_table_to_pandas_inverse():
    df = _sample_df()
    back = to_pandas(to_table(df))
    assert back["mass"][1].to(u.g).value == 2.0
    assert list(back["label"]) == ["a", "b"]


if __name__ == "__main__":
    test_ecsv_roundtrip_preserves_units_and_values()
    test_to_table_to_pandas_inverse()
    print("units round-trip tests passed")
