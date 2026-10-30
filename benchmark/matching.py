"""Pre-registered matching between findings and planted defects (rules in the sealed answer key)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

KEY_PATH = Path(__file__).resolve().parents[1] / "answer_key" / "planted_defects.yaml"

# Oracle grain -> (test family, dimension) used by the matching rule.
GRAIN_FAMILY = {
    "total": ("kpi_total", "total"),
    "region": ("kpi_by_dimension", "region"),
    "category": ("kpi_by_dimension", "category"),
    "product": ("kpi_by_dimension", "product"),
    "cohort_year": ("kpi_by_dimension", "cohort_year"),
    "month": ("kpi_by_period", "month"),
}


@lru_cache(maxsize=1)
def answer_key() -> dict:
    with open(KEY_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _hit(rule_value, value: str) -> bool:
    if rule_value == "*":
        return True
    if isinstance(rule_value, list):
        return value in rule_value
    return value == rule_value


def matches(defect_id: str, kpi: str, family: str, dimension: str) -> bool:
    for rule in answer_key()["defects"][defect_id]["signature"]:
        if _hit(rule["kpi"], kpi) and _hit(rule["family"], family) and _hit(rule["dimension"], dimension):
            return True
    return False


def matching_defects(defect_ids: list[str], kpi: str, family: str, dimension: str) -> list[str]:
    return [d for d in defect_ids if matches(d, kpi, family, dimension)]
