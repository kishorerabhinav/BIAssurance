import zipfile

import pytest

from biwb.safety.file_guard import UnsafeFileError, extract_twbx, parse_xml_safely, validate_upload

MINIMAL_TWB = b"<?xml version='1.0' encoding='utf-8' ?><workbook version='18.1'><datasources/></workbook>"


def test_parses_plain_workbook_xml():
    root = parse_xml_safely(MINIMAL_TWB)
    assert root.tag == "workbook"
    assert root.sourceline == 1


@pytest.mark.parametrize(
    "payload",
    [
        # External entity (XXE)
        b"<?xml version='1.0'?><!DOCTYPE w [<!ENTITY x SYSTEM 'file:///C:/Windows/win.ini'>]>"
        b"<workbook>&x;</workbook>",
        # Billion laughs
        b"<?xml version='1.0'?><!DOCTYPE lolz [<!ENTITY lol 'lol'>"
        b"<!ENTITY lol2 '&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;'>]><workbook>&lol2;</workbook>",
        # Any DTD at all
        b"<?xml version='1.0'?><!DOCTYPE workbook><workbook/>",
        # Not well-formed
        b"<workbook><unclosed></workbook>",
    ],
)
def test_rejects_dangerous_or_malformed_xml(payload):
    with pytest.raises(UnsafeFileError):
        parse_xml_safely(payload)


def test_validate_upload_rules(tmp_path):
    good = tmp_path / "a.twb"
    good.write_bytes(MINIMAL_TWB)
    validate_upload(good)

    bad_ext = tmp_path / "a.xml"
    bad_ext.write_bytes(MINIMAL_TWB)
    with pytest.raises(UnsafeFileError, match="unsupported"):
        validate_upload(bad_ext)

    empty = tmp_path / "e.twb"
    empty.write_bytes(b"")
    with pytest.raises(UnsafeFileError, match="empty"):
        validate_upload(empty)

    with pytest.raises(UnsafeFileError, match="limit"):
        validate_upload(good, max_bytes=10)


def _make_twbx(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


def test_extracts_valid_package(tmp_path):
    pkg = _make_twbx(tmp_path / "w.twbx", {"Sales.twb": MINIMAL_TWB, "Data/orders.csv": b"a,b\n1,2\n"})
    result = extract_twbx(pkg, tmp_path / "out")
    assert result.workbook_path.name == "Sales.twb"
    assert result.workbook_path.read_bytes() == MINIMAL_TWB
    assert (tmp_path / "out" / "Data" / "orders.csv").exists()


@pytest.mark.parametrize(
    ("members", "match"),
    [
        ({"../evil.twb": MINIMAL_TWB}, "traversal"),
        ({"Sales.twb": MINIMAL_TWB, "Data/../../evil.txt": b"x"}, "traversal"),
        ({"/abs.twb": MINIMAL_TWB}, "absolute"),
        ({"C:/abs.twb": MINIMAL_TWB}, "absolute"),
        ({"Data/orders.csv": b"x"}, "exactly one"),
        ({"A.twb": MINIMAL_TWB, "B.twb": MINIMAL_TWB}, "exactly one"),
        ({"Sales.twb": MINIMAL_TWB, "Data/bomb.bin": b"\0" * 5_000_000}, "ratio"),
    ],
)
def test_rejects_unsafe_packages(tmp_path, members, match):
    pkg = _make_twbx(tmp_path / "w.twbx", members)
    with pytest.raises(UnsafeFileError, match=match):
        extract_twbx(pkg, tmp_path / "out")
    assert not (tmp_path / "evil.twb").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_rejects_non_zip(tmp_path):
    fake = tmp_path / "w.twbx"
    fake.write_bytes(b"not a zip")
    with pytest.raises(UnsafeFileError, match="ZIP"):
        extract_twbx(fake, tmp_path / "out")
