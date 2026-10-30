"""Defensive handling of uploaded workbook files (.twb XML and .twbx ZIP packages).

Threats handled: oversized files, XML entity expansion / external entities (XXE), network
fetches during parsing, ZIP path traversal ("zip slip"), absolute paths, symlinks, ZIP bombs.
"""

from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import defusedxml.ElementTree as safe_et
from defusedxml import DefusedXmlException
from lxml import etree

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ZIP_MEMBERS = 2_000
MAX_ZIP_TOTAL_UNCOMPRESSED = 500 * 1024 * 1024
MAX_ZIP_RATIO = 200  # uncompressed / compressed, per member
ALLOWED_SUFFIXES = {".twb", ".twbx"}


class UnsafeFileError(ValueError):
    """The file was rejected before or during parsing."""


@dataclass(frozen=True)
class ExtractedPackage:
    workbook_path: Path
    members: list[str]


def validate_upload(path: Path, *, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise UnsafeFileError(f"unsupported file type {path.suffix!r}; expected .twb or .twbx")
    if not path.is_file():
        raise UnsafeFileError(f"not a file: {path.name}")
    size = path.stat().st_size
    if size == 0:
        raise UnsafeFileError("file is empty")
    if size > max_bytes:
        raise UnsafeFileError(f"file is {size} bytes; limit is {max_bytes}")


def parse_xml_safely(data: bytes) -> etree._Element:
    """Parse untrusted XML. DTDs and entities are rejected outright, then lxml parses with
    entity resolution and network access disabled (defence in depth)."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsafeFileError("XML document exceeds size limit")
    try:
        safe_et.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as err:
        raise UnsafeFileError(f"XML rejected: {type(err).__name__}") from err
    except safe_et.ParseError as err:
        raise UnsafeFileError(f"XML is not well-formed: {err}") from err

    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False,
        huge_tree=False, remove_blank_text=False,
    )
    try:
        return etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as err:
        raise UnsafeFileError(f"XML is not well-formed: {err}") from err


def _check_member(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename.replace("\\", "/")
    member = PurePosixPath(name)
    if member.is_absolute() or name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise UnsafeFileError(f"absolute path in package: {info.filename}")
    if ".." in member.parts:
        raise UnsafeFileError(f"path traversal in package: {info.filename}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise UnsafeFileError(f"symbolic link in package: {info.filename}")
    if info.compress_size and info.file_size / info.compress_size > MAX_ZIP_RATIO:
        raise UnsafeFileError(f"suspicious compression ratio: {info.filename}")
    return member


def extract_twbx(path: Path, dest_dir: Path) -> ExtractedPackage:
    """Validate every member, then extract into dest_dir. Exactly one root-level .twb required."""
    validate_upload(path)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as err:
        raise UnsafeFileError("not a valid .twbx (ZIP) package") from err

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_MEMBERS:
            raise UnsafeFileError(f"package has {len(infos)} members; limit is {MAX_ZIP_MEMBERS}")
        if sum(i.file_size for i in infos) > MAX_ZIP_TOTAL_UNCOMPRESSED:
            raise UnsafeFileError("package uncompressed size exceeds limit")
        members = [_check_member(i) for i in infos]

        root_workbooks = [m for m in members if len(m.parts) == 1 and m.suffix.lower() == ".twb"]
        if len(root_workbooks) != 1:
            raise UnsafeFileError(f"expected exactly one root .twb, found {len(root_workbooks)}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_root = dest_dir.resolve()
        for info, member in zip(infos, members, strict=True):
            if info.is_dir():
                continue
            target = (dest_root / Path(*member.parts)).resolve()
            if not target.is_relative_to(dest_root):
                raise UnsafeFileError(f"path escapes destination: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                remaining = MAX_ZIP_TOTAL_UNCOMPRESSED
                while chunk := src.read(1024 * 1024):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise UnsafeFileError("member larger than declared size")
                    out.write(chunk)

    return ExtractedPackage(
        workbook_path=dest_root / root_workbooks[0].name,
        members=[str(m) for m in members],
    )
