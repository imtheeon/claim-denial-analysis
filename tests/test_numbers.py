"""Every headline number in the README must match the saved output files, and those must match the data."""
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
KPI = pd.read_csv(ROOT / "outputs" / "01_kpis.csv").iloc[0]
MATRIX = pd.read_csv(ROOT / "outputs" / "10_doc_auth_matrix.csv")
CLEAN = ROOT / "data" / "clean" / "claims.parquet"


def shown(value, places=1):
    """True if the README prints this value, allowing for the CSV having been rounded to 4 digits first."""
    step = 10 ** -places
    return any(f"{value + k * step:.{places}f}%" in README for k in (-1, 0, 1))


def test_kpi_identities():
    assert KPI["denied"] / KPI["adjudicated"] == pytest.approx(KPI["denial_rate"], abs=5e-5)
    assert KPI["denied"] <= KPI["adjudicated"] <= KPI["total_claims"]
    assert KPI["recoverable_usd"] <= KPI["denied_usd"]


def test_readme_headline_matches_kpis():
    assert f"${KPI['denied_usd'] / 1e6:.1f}M" in README
    assert f"{KPI['denial_rate'] * 100:.1f}%" in README
    assert f"${KPI['recoverable_usd'] / 1e6:.1f}M" in README


def test_documentation_split_matches_readme():
    all_claims = MATRIX[MATRIX["part"].str.startswith("A")].set_index("doc_group")
    low = all_claims.loc["low doc (<0.7)"]
    high = all_claims.loc["adequate doc (>=0.7)"]
    assert shown(low["denial_rate"] * 100)
    assert shown(high["denial_rate"] * 100)
    assert shown(low["share_of_denied_usd"] * 100, 0)
    assert low["share_of_claims"] + high["share_of_claims"] == pytest.approx(1, abs=1e-3)


@pytest.mark.skipif(not CLEAN.exists(), reason="cleaned data not in the repo")
def test_kpis_recompute_from_the_data():
    got = duckdb.sql(f"SELECT count(*) FROM '{CLEAN}'").fetchone()[0]
    assert got == KPI["total_claims"]
