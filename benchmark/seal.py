"""Seal and verify the answer key (LF-normalised SHA-256, so the hash is identical on every OS)."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "answer_key" / "planted_defects.yaml"
SEAL = ROOT / "answer_key" / "SEALED.sha256"


def digest(path: Path = KEY) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def write_seal() -> str:
    h = digest()
    SEAL.write_text(f"{h}  planted_defects.yaml\n", encoding="utf-8", newline="\n")
    return h


def recorded() -> str:
    return SEAL.read_text(encoding="utf-8").split()[0]


def verify() -> bool:
    return SEAL.exists() and recorded() == digest()


if __name__ == "__main__":
    import sys

    if "--write" in sys.argv:
        if SEAL.exists():
            raise SystemExit("seal already exists; re-sealing requires a documented key revision")
        print(write_seal())
    elif "--revise" in sys.argv:
        # Only for a revision recorded in the key's `revisions:` list (checked by the tests).
        print(write_seal())
    else:
        print("OK" if verify() else "MISMATCH")
        raise SystemExit(0 if verify() else 1)
