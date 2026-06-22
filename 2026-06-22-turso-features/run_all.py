"""Run every claim_*.py and stitch the outputs into a single Markdown report."""
from __future__ import annotations

import importlib
import io
import platform
import sys
from contextlib import redirect_stdout

# Windows console is cp932 by default; force utf-8 so em-dashes and the rest
# of the report survive.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CLAIMS = [
    "claim_1_compat",
    "claim_2_concurrent",
    "claim_3_cdc",
    "claim_4_vector",
]


def env_header():
    try:
        import turso  # noqa: F401
        try:
            ver = importlib.metadata.version("pyturso")
        except Exception:
            ver = "unknown"
    except Exception:
        ver = "import failed"
    print("# turso-features-check — results\n")
    print(f"- platform: {platform.platform()}")
    print(f"- python:   {sys.version.split()[0]}")
    print(f"- pyturso:  {ver}\n")
    print("---\n")


def main():
    env_header()
    for name in CLAIMS:
        buf = io.StringIO()
        try:
            mod = importlib.import_module(name)
            with redirect_stdout(buf):
                mod.main()
            print(buf.getvalue())
        except Exception as e:
            print(f"# {name}\n\nFAILED to run: {type(e).__name__}: {e}\n")
        print("---\n")


if __name__ == "__main__":
    main()
