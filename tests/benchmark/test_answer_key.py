from benchmark import matching, seal
from demo.generator.defects import BENIGN, DEFECTS
from demo.generator.scenarios import SCENARIOS


def test_answer_key_seal_unchanged():
    assert seal.SEAL.exists(), "answer key has not been sealed"
    assert seal.verify(), "planted_defects.yaml changed after sealing"


def test_every_revision_is_documented():
    key = matching.answer_key()
    revisions = key.get("revisions", [])
    assert [r["version"] for r in revisions] == list(range(2, key["version"] + 1))
    assert all(r["reason"].strip() for r in revisions)


def test_seal_ignores_line_endings(tmp_path):
    lf = tmp_path / "lf.yaml"
    crlf = tmp_path / "crlf.yaml"
    lf.write_bytes(b"a: 1\nb: 2\n")
    crlf.write_bytes(b"a: 1\r\nb: 2\r\n")
    assert seal.digest(lf) == seal.digest(crlf)


def test_key_covers_every_generator_defect_and_scenario():
    key = matching.answer_key()
    assert set(key["defects"]) == set(DEFECTS)
    assert set(key["benign"]) == set(BENIGN)
    assert set(key["scenarios"]) | set(key["benign"]) == set(SCENARIOS)
    for sid, spec in key["scenarios"].items():
        assert tuple(spec["defects"]) == tuple(sorted(SCENARIOS[sid].defects)), sid


def test_every_defect_has_signature_and_probe():
    for d, spec in matching.answer_key()["defects"].items():
        assert spec["signature"], d
        assert spec["expected_probe"], d


def test_matching_rule_examples():
    assert matching.matches("D8", "net_revenue", "kpi_by_dimension", "region")
    assert not matching.matches("D8", "net_revenue", "kpi_total", "total")
    assert matching.matches("D6", "gross_profit", "kpi_by_dimension", "category")
    assert not matching.matches("D6", "gross_profit", "kpi_by_dimension", "region")
    assert matching.matches("D7", "return_rate", "kpi_by_period", "month")
    assert not matching.matches("D7", "net_revenue", "kpi_by_period", "month")
