"""Claim 3: Change Data Capture (CDC) for real-time tracking of changes.

The README advertises CDC as a top-level feature, but doesn't give a
Python example. We poke at the API to see (1) whether a CDC entry point
is exposed in pyturso, and (2) if so, what shape it returns for a simple
INSERT / UPDATE / DELETE.

If nothing obvious is exposed, we report that and stop — that's the
honest result for a beta feature whose Python binding is not documented.
"""
from __future__ import annotations

import os
import tempfile
import traceback

import turso


def main():
    print("# Claim 3: Change Data Capture (CDC)\n")

    print("## API surface discovery\n")
    # What does the python module expose at top level?
    members = [m for m in dir(turso) if not m.startswith("_")]
    print(f"- `turso.*` top-level names: {members}\n")

    # Try to connect and see what the connection / cursor expose.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    try:
        con = turso.connect(path)
        con_attrs = sorted(m for m in dir(con) if not m.startswith("_"))
        cur = con.cursor()
        cur_attrs = sorted(m for m in dir(cur) if not m.startswith("_"))
        print(f"- connection attributes: {con_attrs}")
        print(f"- cursor attributes:     {cur_attrs}\n")

        # CDC-shaped names to look for
        cdc_hints = [
            a for a in con_attrs + cur_attrs
            if any(k in a.lower() for k in ("cdc", "change", "subscribe", "stream", "log"))
        ]
        if cdc_hints:
            print(f"- CDC-shaped attributes found: {cdc_hints}\n")
        else:
            print("- no CDC-shaped attributes on connection or cursor\n")

        # Try the SQL-side surface. libsql / turso sometimes expose CDC
        # via PRAGMA or a system table.
        print("## SQL-side probes\n")
        sql_probes = [
            "PRAGMA cdc",
            "PRAGMA cdc_enabled",
            "SELECT * FROM turso_cdc LIMIT 1",
            "SELECT * FROM sqlite_cdc LIMIT 1",
            "SELECT * FROM __turso_cdc LIMIT 1",
            "SELECT name FROM sqlite_master WHERE name LIKE '%cdc%'",
        ]
        for sql in sql_probes:
            try:
                rows = cur.execute(sql).fetchall()
                print(f"- `{sql}` → {rows}")
            except Exception as e:
                print(f"- `{sql}` → ERR: {type(e).__name__}: {e}")

        # End-to-end: make some changes and see whether CDC catches them.
        print("\n## Minimal end-to-end attempt\n")
        cur.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        cur.execute("INSERT INTO t (v) VALUES ('a')")
        cur.execute("INSERT INTO t (v) VALUES ('b')")
        cur.execute("UPDATE t SET v='B' WHERE id=2")
        cur.execute("DELETE FROM t WHERE id=1")
        print("- ran INSERT / INSERT / UPDATE / DELETE on table `t`")
        rows = cur.execute("SELECT name FROM sqlite_master").fetchall()
        print(f"- sqlite_master after changes: {rows}")

    except Exception as e:
        print(f"\nCDC probe failed: {type(e).__name__}: {e}")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
