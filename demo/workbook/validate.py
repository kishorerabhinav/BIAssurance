"""Static checks that a generated workbook satisfies Tableau's XML content models.

Tableau validates workbooks against an internal schema it does not ship as a file. The rules here
are copied from Tableau's own load errors and from Tableau-authored files (the .tds data sources
that ship with Tableau Desktop 2026.3), and they grow whenever Tableau rejects a generated file.
They catch known mistakes quickly; they do not replace the live Tableau load check
(tableau_check.py), which is the final gate.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

FCP = re.compile(r"^_\.fcp\.[A-Za-z0-9]+\.(true|false)\.\.\.")

# Source: Tableau 2026.3 load error D2E8DA72 (2026-10-30), content model for <datasource>.
DATASOURCE_MODEL = [
    "repository-location", "connection", "utility-dimensions", "dimension", "overridable-settings", "aliases",
    "column", "column-instance", "group", "mapped-images", "drill-paths", "unlinked-server-hierarchies",
    "folders-common", "folders-parameters", "actions", "calculated-members", "extract", "layout", "style",
    "semantic-values", "date-options", "default-date-format", "default-sorts", "field-sort-info",
    "datasource-dependencies", "explainability", "filter", "object-graph",
]
# Source: same error, content model for <window>.
WINDOW_MODELS = {
    "worksheet": (["cards", "viewpoint", "simple-id"], {"cards", "simple-id"}),
    "dashboard": (["viewpoints", "active", "device-preview", "simple-id"], {"viewpoints", "active", "simple-id"}),
}


@dataclass(frozen=True)
class Problem:
    line: int
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}"


def base_tag(tag: str) -> str:
    return FCP.sub("", tag)


def _check_sequence(el, model: list[str], required: set[str], what: str) -> list[Problem]:
    problems = []
    last = -1
    seen = set()
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = base_tag(child.tag)
        seen.add(tag)
        if tag not in model:
            problems.append(Problem(child.sourceline, f"<{tag}> is not allowed in {what}"))
            continue
        idx = model.index(tag)
        if idx < last:
            problems.append(Problem(child.sourceline, f"<{tag}> is out of order in {what} "
                                                      f"(must come before <{model[last]}>)"))
        last = max(last, idx)
    for tag in sorted(required - seen):
        problems.append(Problem(el.sourceline, f"{what} is missing required <{tag}>"))
    return problems


def check_tree(root) -> list[Problem]:
    problems = []
    if root.tag != "workbook":
        return [Problem(root.sourceline, "root element must be <workbook>")]
    for ds in root.findall("datasources/datasource"):
        problems += _check_sequence(ds, DATASOURCE_MODEL, set(), f"datasource '{ds.get('name')}'")
    for win in root.findall("windows/window"):
        model = WINDOW_MODELS.get(win.get("class"))
        if model:
            problems += _check_sequence(win, model[0], model[1], f"window '{win.get('name')}'")
    sheets = {w.get("name") for w in root.findall("worksheets/worksheet")}
    dashboards = {d.get("name") for d in root.findall("dashboards/dashboard")}
    windows = {w.get("name") for w in root.findall("windows/window")}
    for name in sorted((sheets | dashboards) - windows):
        problems.append(Problem(0, f"sheet '{name}' has no <window>"))
    for z in root.iter("zone"):
        if z.get("name") and z.get("name") not in sheets:
            problems.append(Problem(z.sourceline, f"dashboard zone refers to unknown sheet '{z.get('name')}'"))
    return problems


def check_twbx(path: Path) -> list[Problem]:
    with zipfile.ZipFile(path) as z:
        twbs = [n for n in z.namelist() if "/" not in n and n.lower().endswith(".twb")]
        if len(twbs) != 1:
            return [Problem(0, f"package must contain exactly one root .twb, found {len(twbs)}")]
        data = z.read(twbs[0])
        missing = []
        root = etree.fromstring(data)
        for conn in root.iter("connection"):
            directory, filename = conn.get("directory"), conn.get("filename")
            if conn.get("class") == "textscan" and directory and filename:
                member = f"{directory}/{filename}"
                if member not in z.namelist():
                    missing.append(Problem(conn.sourceline, f"packaged data file missing: {member}"))
    return missing + check_tree(root)
