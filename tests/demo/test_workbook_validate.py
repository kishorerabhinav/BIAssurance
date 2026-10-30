from lxml import etree

from demo.workbook.build_twb import write_twbx
from demo.workbook.validate import check_tree, check_twbx


def _wb(datasource_children: str, window_children: str = "<cards/><simple-id uuid='{x}'/>") -> etree._Element:
    return etree.fromstring(
        f"<workbook><datasources><datasource name='d'>{datasource_children}</datasource></datasources>"
        f"<worksheets><worksheet name='S'/></worksheets>"
        f"<windows><window class='worksheet' name='S'>{window_children}</window></windows></workbook>")


def test_accepts_tableau_order():
    assert check_tree(_wb("<connection/><aliases/><column/><layout/><semantic-values/><filter/>"
                          "<_.fcp.ObjectModelEncapsulateLegacy.true...object-graph/>")) == []


def test_rejects_filter_before_layout():
    # The exact mistake Tableau rejected on 2026-10-30 (error D2E8DA72).
    problems = check_tree(_wb("<connection/><filter/><layout/>"))
    assert any("<layout> is out of order" in p.message for p in problems)


def test_rejects_window_without_cards():
    problems = check_tree(_wb("<connection/>", "<simple-id uuid='{x}'/>"))
    assert any("missing required <cards>" in p.message for p in problems)


def test_rejects_unknown_datasource_child():
    assert any("not allowed" in p.message for p in check_tree(_wb("<connection/><bogus/>")))


def test_generated_package_passes(tmp_path):
    from demo.generator.io import load_schema

    csv = tmp_path / "csv"
    csv.mkdir()
    for table, spec in load_schema("legacy_schema")["tables"].items():
        (csv / f"{table}.csv").write_text(",".join(spec["columns"]) + "\n", encoding="utf-8")
    assert check_twbx(write_twbx(csv, tmp_path / "w.twbx")) == []
    assert check_twbx(write_twbx(csv, tmp_path / "g" / "w.twbx", gate=True)) == []
