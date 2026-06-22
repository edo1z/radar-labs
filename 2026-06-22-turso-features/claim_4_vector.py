"""Claim 4: Vector support — exact search and vector manipulation.

We use 2D vectors so the expected ordering is obvious by inspection.
Each vector is an arrow from the origin; cosine distance measures the
angle between two arrows, so the further the arrow has rotated from
the query, the larger the distance.

  id 1: [ 1,  0]   →   ( 0° from query)
  id 2: [ 1,  1]   ↗   (45° from query)
  id 3: [ 0,  1]   ↑   (90° from query)
  id 4: [-1,  0]   ←   (180° from query, opposite direction)

Query: [1, 0] — same as id 1.
Expected order by cosine distance: 1, 2, 3, 4.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import traceback

import turso


SAMPLE = [
    (1, [1.0, 0.0]),    # 0 degrees from query
    (2, [1.0, 1.0]),    # 45 degrees
    (3, [0.0, 1.0]),    # 90 degrees
    (4, [-1.0, 0.0]),   # 180 degrees (opposite)
]
QUERY = [1.0, 0.0]
EXPECTED_ORDER = [1, 2, 3, 4]


def fresh(suffix: str):
    fd, p = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    os.remove(p)
    return p


def try_turso():
    print("## turso\n")
    path = fresh(".db")
    try:
        con = turso.connect(path)
        cur = con.cursor()
        cur.execute("CREATE TABLE v (id INTEGER PRIMARY KEY, e F32_BLOB(2))")
        for vid, vec in SAMPLE:
            cur.execute(
                "INSERT INTO v (id, e) VALUES (?, vector(?))",
                (vid, str(vec)),
            )
        rows = cur.execute(
            "SELECT id, vector_distance_cos(e, vector(?)) AS d FROM v ORDER BY d",
            (str(QUERY),),
        ).fetchall()

        print(f"- ordered result: {rows}")
        order = [r[0] for r in rows]
        if order == EXPECTED_ORDER:
            print(f"- order matches expectation {EXPECTED_ORDER} ✓\n")
        else:
            print(f"- order {order} did NOT match expectation {EXPECTED_ORDER}\n")
    except Exception as e:
        print(f"- failed: {type(e).__name__}: {e}\n")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def try_sqlite():
    print("## sqlite3 (contrast)\n")
    print("- sqlite3 has no native vector type; you'd need an extension")
    print("  like sqlite-vec / sqlite-vss. We don't load one here.\n")


def main():
    print("# Claim 4: Vector support\n")
    print("Sample vectors (2D arrows from origin):")
    arrows = {0: "→", 1: "↗", 2: "↑", 3: "←"}
    angles = [0, 45, 90, 180]
    for i, (vid, vec) in enumerate(SAMPLE):
        print(f"  id {vid}: {vec}  {arrows[i]}  ({angles[i]}° from query)")
    print(f"Query: {QUERY}  (same direction as id 1)")
    print(f"Expected order by cosine distance: {EXPECTED_ORDER}\n")
    try_turso()
    try_sqlite()


if __name__ == "__main__":
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
