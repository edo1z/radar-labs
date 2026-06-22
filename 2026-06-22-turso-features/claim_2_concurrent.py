"""Claim 2: BEGIN CONCURRENT improves write throughput via MVCC.

We compare wall-clock time and committed-row count for the same insert
workload across four configurations:

  1. stock sqlite3 (WAL, serialized writers)
  2. turso with `BEGIN`                       — no MVCC
  3. turso with `BEGIN CONCURRENT`            — no MVCC (expected to error)
  4. turso with `BEGIN CONCURRENT` + MVCC     — `PRAGMA journal_mode='mvcc'`

The workload is K threads, each inserting N rows into its own table.
Threads write to disjoint rows, so any conflict here comes from the
writer-lock model, not row-level conflicts.

The undocumented bit we had to grep for: pyturso 0.6.1 only accepts
`BEGIN CONCURRENT` when MVCC is enabled, and MVCC is enabled via
`PRAGMA journal_mode = 'mvcc'`. The README does not say this; we found it
in `scripts/turso-mvcc-sqlite3` in the upstream repo.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import traceback

import turso


K_THREADS = 8
N_PER_THREAD = 2000  # keep small enough that the run finishes quickly


def fresh_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def run_sqlite_baseline():
    path = fresh_path()
    try:
        con = sqlite3.connect(path, check_same_thread=False, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        for i in range(K_THREADS):
            con.execute(f"CREATE TABLE t{i} (id INTEGER PRIMARY KEY, v INTEGER)")
        con.commit()

        errors: list[str] = []
        succeeded = [0] * K_THREADS

        def worker(tid):
            c = sqlite3.connect(path, timeout=30)
            try:
                c.execute("BEGIN")
                for i in range(N_PER_THREAD):
                    try:
                        c.execute(f"INSERT INTO t{tid} (v) VALUES (?)", (i,))
                        succeeded[tid] += 1
                    except Exception as e:
                        errors.append(f"thread {tid} insert: {type(e).__name__}: {e}")
                        break
                c.execute("COMMIT")
            except Exception as e:
                errors.append(f"thread {tid} commit: {type(e).__name__}: {e}")
            finally:
                c.close()

        t0 = time.perf_counter()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(K_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        t1 = time.perf_counter()

        total = con.execute(
            "SELECT " + " + ".join(f"(SELECT count(*) FROM t{i})" for i in range(K_THREADS))
        ).fetchone()[0]
        con.close()
        return t1 - t0, total, errors
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def run_turso(begin_stmt: str, enable_mvcc: bool):
    path = fresh_path()
    try:
        con = turso.connect(path)
        cur = con.cursor()
        if enable_mvcc:
            cur.execute("PRAGMA journal_mode = 'mvcc'")
        for i in range(K_THREADS):
            cur.execute(f"CREATE TABLE t{i} (id INTEGER PRIMARY KEY, v INTEGER)")

        errors: list[str] = []
        succeeded = [0] * K_THREADS

        def worker(tid):
            try:
                c = turso.connect(path)
                if enable_mvcc:
                    try:
                        c.cursor().execute("PRAGMA journal_mode = 'mvcc'")
                    except Exception:
                        pass
                cur2 = c.cursor()
                try:
                    cur2.execute(begin_stmt)
                except Exception as e:
                    errors.append(f"thread {tid} {begin_stmt}: {type(e).__name__}: {e}")
                    return
                for i in range(N_PER_THREAD):
                    try:
                        cur2.execute(f"INSERT INTO t{tid} (v) VALUES (?)", (i,))
                        succeeded[tid] += 1
                    except Exception as e:
                        errors.append(f"thread {tid} insert {i}: {type(e).__name__}: {e}")
                        break
                try:
                    cur2.execute("COMMIT")
                except Exception as e:
                    errors.append(f"thread {tid} COMMIT: {type(e).__name__}: {e}")
            except Exception as e:
                errors.append(f"thread {tid} setup: {type(e).__name__}: {e}")

        t0 = time.perf_counter()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(K_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        t1 = time.perf_counter()

        try:
            total = cur.execute(
                "SELECT " + " + ".join(f"(SELECT count(*) FROM t{i})" for i in range(K_THREADS))
            ).fetchone()[0]
        except Exception as e:
            total = f"(count failed: {type(e).__name__}: {e})"
        return t1 - t0, total, errors
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def summarize_errors(errors: list[str], limit: int = 2) -> str:
    if not errors:
        return "no errors"
    # collapse identical-ish errors
    seen: dict[str, int] = {}
    for e in errors:
        # drop the per-iteration index for grouping
        key = e.split(":", 2)[-1].strip() if "insert" in e else e
        seen[key] = seen.get(key, 0) + 1
    parts = sorted(seen.items(), key=lambda kv: -kv[1])
    return "; ".join(f"{c}× {k[:80]}" for k, c in parts[:limit])


def main():
    print("# Claim 2: BEGIN CONCURRENT for write throughput\n")
    print(f"Workload: {K_THREADS} threads × {N_PER_THREAD} INSERTs into disjoint tables\n")

    runs = [
        ("sqlite3 (WAL, BEGIN)",      lambda: run_sqlite_baseline()),
        ("turso BEGIN, no MVCC",      lambda: run_turso("BEGIN", enable_mvcc=False)),
        ("turso BEGIN CONCURRENT, no MVCC",
                                       lambda: run_turso("BEGIN CONCURRENT", enable_mvcc=False)),
        ("turso BEGIN CONCURRENT, MVCC on",
                                       lambda: run_turso("BEGIN CONCURRENT", enable_mvcc=True)),
    ]

    rows = []
    for label, fn in runs:
        try:
            dt, total, errors = fn()
            target = K_THREADS * N_PER_THREAD
            rate = target / dt if dt > 0 else 0
            rows.append((label, f"{dt:.3f}s", f"{rate:,.0f} ins/s",
                         f"committed {total}/{target}",
                         summarize_errors(errors)))
        except Exception as e:
            rows.append((label, "ERR", "-", "-", f"{type(e).__name__}: {e}"))

    print("| Engine | Wall | Throughput (target) | Committed | Notes |")
    print("| ------ | ---- | ------------------- | --------- | ----- |")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")


if __name__ == "__main__":
    # Force UTF-8 stdout on Windows so em-dashes survive
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
