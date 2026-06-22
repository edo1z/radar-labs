# turso-features-check — results

- platform: Windows-11-10.0.26200-SP0
- python:   3.12.10
- pyturso:  unknown

---

# Claim 1: SQLite compatibility

| # | Probe | sqlite3 | turso | same? |
| - | ----- | ------- | ----- | ----- |
| 1 | CREATE / INSERT / SELECT | ok | ok | yes |
| 2 | WHERE + LIKE | ok | ok | yes |
| 3 | JOIN | ok | ok | yes |
| 4 | WITH RECURSIVE (CTE) | ok | ERR: DatabaseError: Parse error: Recursive CTEs are not yet supported | NO |
| 5 | json_extract (JSON1) | ok | ok | yes |
| 6 | FTS5 virtual table | ok | ERR: DatabaseError: Parse error: no such module: fts5 | NO |
| 7 | ALTER TABLE ... ADD COLUMN | ok | ok | yes |
| 8 | ALTER TABLE ... DROP COLUMN | ok | ok | yes |

## Details for diverging probes

### 4. WITH RECURSIVE (CTE)
- sqlite3: [(15,)]
- turso:   DatabaseError: Parse error: Recursive CTEs are not yet supported

### 6. FTS5 virtual table
- sqlite3: [('quick brown fox',)]
- turso:   DatabaseError: Parse error: no such module: fts5


---

# Claim 2: BEGIN CONCURRENT for write throughput

Workload: 8 threads × 2000 INSERTs into disjoint tables

| Engine | Wall | Throughput (target) | Committed | Notes |
| ------ | ---- | ------------------- | --------- | ----- |
| sqlite3 (WAL, BEGIN) | 0.133s | 119,969 ins/s | committed 16000/16000 | no errors |
| turso BEGIN, no MVCC | 0.191s | 83,563 ins/s | committed 8000/16000 | 4× database is locked |
| turso BEGIN CONCURRENT, no MVCC | 0.006s | 2,501,251 ins/s | committed 0/16000 | 1× thread 0 BEGIN CONCURRENT: DatabaseError: Transaction error: Concurrent transact; 1× thread 1 BEGIN CONCURRENT: DatabaseError: Transaction error: Concurrent transact |
| turso BEGIN CONCURRENT, MVCC on | 0.006s | 2,461,690 ins/s | committed 0/16000 | 1× thread 0 BEGIN CONCURRENT: DatabaseError: Transaction error: Concurrent transact; 1× thread 1 BEGIN CONCURRENT: DatabaseError: Transaction error: Concurrent transact |

---

# Claim 3: Change Data Capture (CDC)

## API surface discovery

- `turso.*` top-level names: ['Connection', 'Cursor', 'DataError', 'DatabaseError', 'EncryptionOpts', 'Error', 'IntegrityError', 'InterfaceError', 'InternalError', 'NotSupportedError', 'OperationalError', 'ProgrammingError', 'Row', 'Warning', 'apilevel', 'connect', 'lib', 'logging', 'paramstyle', 'setup_logging', 'sqlite_version', 'sqlite_version_info', 'threadsafety']

- connection attributes: ['DataError', 'DatabaseError', 'Error', 'IntegrityError', 'InterfaceError', 'InternalError', 'NotSupportedError', 'OperationalError', 'ProgrammingError', 'Warning', 'autocommit', 'close', 'commit', 'cursor', 'execute', 'executemany', 'executescript', 'extra_io', 'in_transaction', 'isolation_level', 'rollback', 'row_factory', 'text_factory']
- cursor attributes:     ['arraysize', 'close', 'connection', 'description', 'execute', 'executemany', 'executescript', 'fetchall', 'fetchmany', 'fetchone', 'lastrowid', 'row_factory', 'rowcount', 'setinputsizes', 'setoutputsize']

- no CDC-shaped attributes on connection or cursor

## SQL-side probes

- `PRAGMA cdc` → ERR: DatabaseError: Parse error: Not a valid pragma name
- `PRAGMA cdc_enabled` → ERR: DatabaseError: Parse error: Not a valid pragma name
- `SELECT * FROM turso_cdc LIMIT 1` → ERR: DatabaseError: Parse error: no such table: turso_cdc
- `SELECT * FROM sqlite_cdc LIMIT 1` → ERR: DatabaseError: Parse error: no such table: sqlite_cdc
- `SELECT * FROM __turso_cdc LIMIT 1` → ERR: DatabaseError: Parse error: no such table: __turso_cdc
- `SELECT name FROM sqlite_master WHERE name LIKE '%cdc%'` → []

## Minimal end-to-end attempt

- ran INSERT / INSERT / UPDATE / DELETE on table `t`
- sqlite_master after changes: [('t',)]

---

# Claim 4: Vector support

Sample vectors (2D arrows from origin):
  id 1: [1.0, 0.0]  →  (0° from query)
  id 2: [1.0, 1.0]  ↗  (45° from query)
  id 3: [0.0, 1.0]  ↑  (90° from query)
  id 4: [-1.0, 0.0]  ←  (180° from query)
Query: [1.0, 0.0]  (same direction as id 1)
Expected order by cosine distance: [1, 2, 3, 4]

## turso

- ordered result: [(1, 4.470166414805021e-08), (2, 0.29289324671949435), (3, 1.0), (4, 1.9999999552983359)]
- order matches expectation [1, 2, 3, 4] ✓

## sqlite3 (contrast)

- sqlite3 has no native vector type; you'd need an extension
  like sqlite-vec / sqlite-vss. We don't load one here.


---

