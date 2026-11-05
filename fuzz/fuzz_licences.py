"""Fuzz the checks that read files from upstream sources before they enter the trove.

    pip install atheris && python fuzz/fuzz_licences.py -max_total_time=120

Any exception here is a bug: a hostile upstream file must never stop a learn.
"""

import sys
import tempfile
from pathlib import Path

import atheris

with atheris.instrument_imports():
    from dex_trove.learn import ananke_secret_flags, scan_secrets
    from dex_trove.licenses import classify_file

_FILE = Path(tempfile.mkdtemp()) / "LICENSE"


def one_input(data: bytes) -> None:
    _FILE.write_bytes(data)
    classify_file(_FILE, label="fuzzed")
    scan_secrets({"LICENSE": _FILE})
    ananke_secret_flags({"LICENSE": _FILE})


if __name__ == "__main__":
    atheris.Setup(sys.argv, one_input)
    atheris.Fuzz()
