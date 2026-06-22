# turso-features-check

Trying out each feature the new [Turso database](https://github.com/tursodatabase/turso)
advertises on its README, one at a time, on Windows + Python.

Turso (the in-process Rust rewrite of SQLite, not the cloud service) is in BETA.
This repo doesn't try to evaluate whether it's "ready for production" — that's
too big a claim for a half day of poking. It just runs each headline feature and
writes down what actually happened.

## Claims under test

From the [Turso README](https://github.com/tursodatabase/turso):

| # | Claim | Script |
| - | ----- | ------ |
| 1 | SQLite-compatible (SQL, file format, C API) | `claim_1_compat.py` |
| 2 | `BEGIN CONCURRENT` for write throughput (MVCC) | `claim_2_concurrent.py` |
| 3 | Change Data Capture (CDC) for real-time tracking | `claim_3_cdc.py` |
| 4 | Vector support (exact search and manipulation) | `claim_4_vector.py` |
| 5 | `io_uring` async I/O | not tested — Linux only, this run was on Windows |

## Run

```powershell
uv sync
uv run python claim_1_compat.py
uv run python claim_2_concurrent.py
uv run python claim_3_cdc.py
uv run python claim_4_vector.py
```

Or run everything at once and capture the output:

```powershell
uv run python run_all.py | Tee-Object results.md
```

## Results

See [`results.md`](results.md) for what actually happened on this run.

## Environment

- OS: Windows 11
- Python: 3.10
- Turso: whatever `pyturso` resolves to at install time (recorded in `results.md`)

## License

MIT.
