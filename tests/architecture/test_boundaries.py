"""Architecture boundaries (plan §8.6.1 and §9.2), checked by scanning source code.

1. The engine (src/biwb) never imports or references the answer key, the benchmark or the
   synthetic-data generator, so it cannot "know" the planted defects.
2. Decision-path packages never import the optional AI layer.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "src" / "biwb"
DECISION_PACKAGES = ("validation", "readiness", "calc", "planner", "mapping", "safety", "logic")
FORBIDDEN_ENGINE_IMPORTS = ("answer_key", "benchmark", "demo", "scripts", "tests")
FORBIDDEN_ENGINE_STRINGS = ("answer_key", "planted_defects", "demo/generator", "demo\\generator")


def _py_files(base: Path):
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_engine_has_source_files():
    assert _py_files(ENGINE), "engine package not found"


@pytest.mark.parametrize("path", _py_files(ENGINE), ids=lambda p: str(p.relative_to(ENGINE)))
def test_engine_does_not_import_benchmark_material(path):
    bad = {m for m in _imports(path) if m.split(".")[0] in FORBIDDEN_ENGINE_IMPORTS}
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize("path", _py_files(ENGINE), ids=lambda p: str(p.relative_to(ENGINE)))
def test_engine_does_not_reference_answer_key(path):
    text = path.read_text(encoding="utf-8")
    hits = [s for s in FORBIDDEN_ENGINE_STRINGS if s in text]
    assert not hits, f"{path.name} references {hits}"


def test_engine_sql_migrations_do_not_reference_answer_key():
    for sql in (ENGINE / "persistence" / "migrations").glob("*.sql"):
        text = sql.read_text(encoding="utf-8").lower()
        assert "answer_key" not in text and "planted" not in text


def test_decision_packages_do_not_import_ai():
    offenders = []
    for pkg in DECISION_PACKAGES:
        base = ENGINE / pkg
        if not base.exists():
            continue  # package not built yet; rule applies as soon as it exists
        for path in _py_files(base):
            if any(m == "biwb.ai" or m.startswith("biwb.ai.") or m == "anthropic" for m in _imports(path)):
                offenders.append(str(path.relative_to(ENGINE)))
    assert not offenders, f"decision-path modules import the AI layer: {offenders}"


def test_scanner_detects_forbidden_import(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text("from answer_key import x\nimport biwb.ai.gateway\n", encoding="utf-8")
    assert {"answer_key", "biwb.ai.gateway"} <= _imports(probe)
