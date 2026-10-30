"""Structural checks on the generated demo workbook: it must contain exactly what the build guide
describes, be internally consistent (every reference resolves), and be reproducible."""

import re
from pathlib import Path

import pytest

from biwb.safety.file_guard import extract_twbx, parse_xml_safely
from demo.workbook.build_twb import CALCS, stored_formula, write_twb, write_twbx

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "demo-workbook-build-guide.md"
FCP = "_.fcp.ObjectModelEncapsulateLegacy.true..."


@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory):
    # Headers are all the builder reads from the CSVs; write tiny CSVs with the real headers.
    from demo.generator.io import load_schema

    d = tmp_path_factory.mktemp("csv")
    for table, spec in load_schema("legacy_schema")["tables"].items():
        (d / f"{table}.csv").write_text(",".join(spec["columns"]) + "\n", encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def root(csv_dir, tmp_path_factory):
    path = write_twb(csv_dir, tmp_path_factory.mktemp("twb") / "w.twb", "D:/x/legacy_csv")
    return parse_xml_safely(path.read_bytes())


def _caption_map(root):
    ds = root.find("datasources/datasource[@caption]")
    return {c.get("name"): c.get("caption") for c in ds.findall("column[@caption]")}


def test_guide_formulas_match_generated_calcs():
    text = GUIDE.read_text(encoding="utf-8")
    rows = re.findall(r"^\| \d+ \| `([^`]+)` \| `(.+)` \|$", text, flags=re.M)
    assert len(rows) == 13
    guide = {name: formula for name, formula in rows}
    for c in CALCS:
        expected = re.sub(r"\{\{([^}]+)\}\}", r"[\1]", c.formula)
        assert guide[c.caption] == expected, c.caption


def test_calculations_stored_with_internal_names(root):
    captions = _caption_map(root)
    ds = root.find("datasources/datasource[@caption]")
    calcs = {c.get("caption"): c.find("calculation").get("formula") for c in ds.findall("column[calculation]")}
    assert set(calcs) == {c.caption for c in CALCS}
    line_net = calcs["Line Net"]
    assert "Line Gross" not in line_net and "[Calculation_" in line_net
    resolved = re.sub(r"\[(Calculation_\d+)\]", lambda m: f"[{captions['[' + m.group(1) + ']']}]", line_net)
    assert resolved == "[Line Gross] - [Discount Amount]"
    assert calcs["Customer First Order"] == "{ FIXED [CustNo] : MIN([OrdDt]) }"


def test_every_formula_reference_resolves(root):
    ds = root.find("datasources/datasource[@caption]")
    known = {r.text for r in ds.iter("local-name")} | {c.get("name") for c in ds.findall("column")}
    for c in CALCS:
        for ref in re.findall(r"\[[^\[\]]+\]", stored_formula(c)):
            assert ref in known, (c.caption, ref)


def test_model_structure(root):
    ds = root.find("datasources/datasource[@caption]")
    graph = ds.find(FCP + "object-graph")
    assert [o.get("caption") for o in graph.findall("objects/object")] == ["ORDERS_HDR.csv", "RTN_LOG.csv"]
    assert all("." not in o.get("id") for o in graph.findall("objects/object"))
    joins = graph.findall(".//relation[@type='join']")
    assert sorted(j.get("join") for j in joins) == ["inner", "left", "left", "left", "left"]
    tables = [r.get("name") for r in graph.find("objects/object").iter("relation") if r.get("type") == "table"]
    assert tables == ["ORDERS_HDR.csv", "ord_lines.csv", "PROD_MSTR.csv", "prod_cat.csv", "CUSTMR.csv",
                      "RGN_LKP.csv"]
    (rtn,) = graph.findall("relationships/relationship")
    assert rtn.find("expression").get("op") == "AND"
    assert len(rtn.findall("expression/expression")) == 2
    flt = ds.find("filter")
    assert flt.get("column") == "[OrdStat]"
    assert flt.find("groupfilter").get("function") == "except"
    assert flt.find("groupfilter/groupfilter[@function='member']").get("member") == '"X"'


def test_parameter(root):
    p = root.find("datasources/datasource[@name='Parameters']/column")
    assert (p.get("caption"), p.get("datatype"), p.get("value")) == ("Top N", "integer", "10")
    assert p.find("range").attrib == {"granularity": "5", "max": "50", "min": "5"}


def test_worksheets_filters_and_dashboard(root):
    sheets = {w.get("name"): w for w in root.findall("worksheets/worksheet")}
    assert list(sheets) == ["KPI Summary", "Revenue by Region", "Monthly Trend", "Category Profitability",
                            "Top Products", "Customer Cohorts"]
    for name, ws in sheets.items():
        years = [f for f in ws.findall("table/view/filter") if f.get("column").endswith("[yr:OrdDt:ok]")]
        assert len(years) == 1, name
        assert years[0].find("groupfilter").get("member") == "2025"
        assert (years[0].get("context") == "true") == (name == "Top Products"), name
    top = [f for f in sheets["Top Products"].findall("table/view/filter") if "ProdNm" in f.get("column")][0]
    assert top.find("groupfilter").get("count") == "[Parameters].[Parameter 1]"
    tc = sheets["Monthly Trend"].findall(".//column-instance/table-calc")
    assert len(tc) == 1
    zones = [z.get("name") for z in root.iter("zone") if z.get("name")]
    assert zones == ["KPI Summary", "Revenue by Region", "Monthly Trend", "Category Profitability"]


def test_shelf_references_point_at_declared_instances(root):
    ds_name = root.find("datasources/datasource[@caption]").get("name")
    for ws in root.findall("worksheets/worksheet"):
        declared = {ci.get("name") for ci in ws.iter("column-instance")}
        shelves = " ".join(filter(None, [ws.findtext("table/rows"), ws.findtext("table/cols")]))
        for inner in re.findall(rf"\[{re.escape(ds_name)}\]\.(\[[^\]]+\])", shelves):
            if inner.startswith("[:"):
                continue
            assert inner in declared, (ws.get("name"), inner)


def test_output_is_reproducible(csv_dir, tmp_path):
    a = write_twb(csv_dir, tmp_path / "a.twb").read_bytes()
    b = write_twb(csv_dir, tmp_path / "b.twb").read_bytes()
    assert a == b
    x = write_twbx(csv_dir, tmp_path / "a" / "w.twbx").read_bytes()
    y = write_twbx(csv_dir, tmp_path / "b" / "w.twbx").read_bytes()
    assert x == y


def test_packaged_workbook_is_safe_and_self_contained(csv_dir, tmp_path):
    pkg = write_twbx(csv_dir, tmp_path / "w.twbx")
    result = extract_twbx(pkg, tmp_path / "out")
    root = parse_xml_safely(result.workbook_path.read_bytes())
    conn = root.find(".//named-connection/connection")
    assert conn.get("directory") == "Data/legacy_csv"
    assert (tmp_path / "out" / "Data" / "legacy_csv" / "ORDERS_HDR.csv").exists()
