"""Claim 1: Turso is SQLite-compatible (SQL dialect, file format, C API).

We don't try to certify "compatibility" — we just run a handful of SQL
fragments that work on stock sqlite3 and see whether Turso accepts the
same code unchanged. Each row in the report says: did sqlite3 accept it,
did Turso accept it, were the results the same.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import traceback
from dataclasses import dataclass

import turso  # pyturso


@dataclass
class Probe:
    name: str
    setup: list[str]
    query: str


PROBES: list[Probe] = [
    Probe(
        name="CREATE / INSERT / SELECT",
        setup=[
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)",
            "INSERT INTO users (name) VALUES ('alice'), ('bob'), ('carol')",
        ],
        query="SELECT name FROM users ORDER BY id",
    ),
    Probe(
        name="WHERE + LIKE",
        setup=[
            "CREATE TABLE items (sku TEXT, label TEXT)",
            "INSERT INTO items VALUES ('a1', 'apple'), ('b1', 'banana'), ('a2', 'avocado')",
        ],
        query="SELECT sku FROM items WHERE label LIKE 'a%' ORDER BY sku",
    ),
    Probe(
        name="JOIN",
        setup=[
            "CREATE TABLE author (id INTEGER PRIMARY KEY, name TEXT)",
            "CREATE TABLE book (id INTEGER PRIMARY KEY, author_id INTEGER, title TEXT)",
            "INSERT INTO author VALUES (1, 'Alice'), (2, 'Bob')",
            "INSERT INTO book VALUES (1, 1, 'A1'), (2, 1, 'A2'), (3, 2, 'B1')",
        ],
        query="SELECT a.name, COUNT(b.id) FROM author a LEFT JOIN book b ON b.author_id = a.id GROUP BY a.name ORDER BY a.name",
    ),
    Probe(
        name="WITH RECURSIVE (CTE)",
        setup=[],
        query="WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x < 5) SELECT sum(x) FROM n",
    ),
    Probe(
        name="json_extract (JSON1)",
        setup=[
            "CREATE TABLE doc (j TEXT)",
            "INSERT INTO doc VALUES ('{\"a\":1,\"b\":2}'), ('{\"a\":3}')",
        ],
        query="SELECT json_extract(j, '$.a') FROM doc ORDER BY 1",
    ),
    Probe(
        name="FTS5 virtual table",
        setup=[
            "CREATE VIRTUAL TABLE notes USING fts5(body)",
            "INSERT INTO notes(body) VALUES ('quick brown fox'), ('lazy dog')",
        ],
        query="SELECT body FROM notes WHERE notes MATCH 'fox'",
    ),
    Probe(
        name="ALTER TABLE ... ADD COLUMN",
        setup=[
            "CREATE TABLE t (a INTEGER)",
            "INSERT INTO t VALUES (1), (2)",
            "ALTER TABLE t ADD COLUMN b TEXT DEFAULT 'x'",
        ],
        query="SELECT a, b FROM t ORDER BY a",
    ),
    Probe(
        name="ALTER TABLE ... DROP COLUMN",
        setup=[
            "CREATE TABLE t2 (a INTEGER, b TEXT)",
            "INSERT INTO t2 VALUES (1, 'x')",
            "ALTER TABLE t2 DROP COLUMN b",
        ],
        query="SELECT * FROM t2",
    ),
]


def run_on_sqlite(probe: Probe):
    con = sqlite3.connect(":memory:")
    try:
        for s in probe.setup:
            con.execute(s)
        rows = con.execute(probe.query).fetchall()
        return True, rows, None
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"
    finally:
        con.close()


def run_on_turso(probe: Probe):
    # pyturso doesn't support :memory: in the same way as sqlite3 in all builds,
    # so we use a temp file for safety.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let turso create it fresh
    try:
        con = turso.connect(path)
        cur = con.cursor()
        for s in probe.setup:
            cur.execute(s)
        rows = cur.execute(probe.query).fetchall()
        return True, rows, None
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def fmt(rows):
    if rows is None:
        return "-"
    return repr(rows)


def main():
    print("# Claim 1: SQLite compatibility\n")
    print("| # | Probe | sqlite3 | turso | same? |")
    print("| - | ----- | ------- | ----- | ----- |")
    for i, p in enumerate(PROBES, 1):
        ok_s, rows_s, err_s = run_on_sqlite(p)
        ok_t, rows_t, err_t = run_on_turso(p)
        same = "yes" if (ok_s and ok_t and rows_s == rows_t) else (
            "n/a" if not ok_s else "NO"
        )
        cell_s = "ok" if ok_s else f"ERR: {err_s}"
        cell_t = "ok" if ok_t else f"ERR: {err_t}"
        print(f"| {i} | {p.name} | {cell_s} | {cell_t} | {same} |")

    print("\n## Details for diverging probes\n")
    for i, p in enumerate(PROBES, 1):
        ok_s, rows_s, err_s = run_on_sqlite(p)
        ok_t, rows_t, err_t = run_on_turso(p)
        if ok_s and ok_t and rows_s == rows_t:
            continue
        print(f"### {i}. {p.name}")
        print(f"- sqlite3: {fmt(rows_s) if ok_s else err_s}")
        print(f"- turso:   {fmt(rows_t) if ok_t else err_t}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
