"""The independent oracle must reproduce hand-computed KPI values exactly."""

from pathlib import Path

import pytest
import yaml

from benchmark import oracle

GOLDEN = Path(__file__).resolve().parents[1] / "golden"


@pytest.fixture(scope="module")
def computed():
    lines, products = oracle.legacy_lines(GOLDEN / "legacy")
    return oracle.all_kpis(lines, products)


def _cases():
    expected = yaml.safe_load((GOLDEN / "expected.yaml").read_text(encoding="utf-8"))
    for grain, segments in expected.items():
        for segment, values in segments.items():
            for kpi, value in values.items():
                yield grain, str(segment), kpi, value


@pytest.mark.parametrize(("grain", "segment", "kpi", "value"), list(_cases()))
def test_oracle_matches_hand_computed(computed, grain, segment, kpi, value):
    assert computed[grain].at[segment, kpi] == pytest.approx(value, abs=1e-9)


def test_golden_segments_are_complete(computed):
    expected = yaml.safe_load((GOLDEN / "expected.yaml").read_text(encoding="utf-8"))
    for grain, segments in expected.items():
        assert set(computed[grain].index) == {str(s) for s in segments}, grain


def test_fixed_lod_respects_filter_order(computed):
    # Cancelled 2024 order O4 must not make C2 a 2024 customer (data source filter before FIXED),
    # while the 2025 worksheet filter must not stop C1's 2024 order defining its cohort.
    cohorts = computed["cohort_year"]
    assert cohorts.at["2024", "net_revenue"] == 325
    assert cohorts.at["2025", "net_revenue"] == 350
