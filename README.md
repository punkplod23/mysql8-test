# MySQL InnoDB Concurrency & Deadlock Test Suite

Testing various strategies to handle concurrent writes and deadlock prevention in MySQL 8.4 with InnoDB.

## Latest Test Run

**Job:** [GitHub Actions Run #80446459447](https://github.com/punkplod23/mysql8-test/actions/runs/27241628045/job/80446459447)

### Results Summary

| Test | Strategy | Status | Deadlocks | Duration |
|------|----------|--------|-----------|----------|
| Test 1 | Standard (REPEATABLE READ, no locks) | ❌ FAILED | 10 | 0.32s |
| Test 2 | Table-Level Locking (WRITE) | ✅ PASSED | 0 | 0.44s |
| Test 3 | READ COMMITTED isolation | ✅ PASSED | 0 | 0.41s |
| Test 4 | REPLACE INTO (no locks) | ❌ FAILED | 12 | 0.94s |
| Test 5 | REPLACE INTO + table locks | ✅ PASSED | 0 | 2.35s |
| Test 6 | REPEATABLE READ + retry logic | ✅ PASSED | 0 | 0.48s |
| Test 7 | Single-threaded baseline | ✅ PASSED | 0 | 0.05s |

## Root Cause Analysis

### Deadlock Pattern (Tests 1 & 4)
- **Isolation Level:** REPEATABLE READ enables gap locking
- **Trigger:** 14 concurrent threads hitting overlapping row ranges via UNIQUE KEY constraint
- **Mechanism:** Circular wait on gap locks → errno 1213 (Deadlock detected)
- **Predictability:** Consistent; same threads (0-10) deadlock each run

### Solutions That Work

**Option 1: Relaxed Isolation (RECOMMENDED)**
- Use `READ COMMITTED` isolation (Test 3)
- Eliminates gap locking, prevents deadlocks
- Performance: 0.41s (same speed as single-threaded, 100% reliable)
- Concurrency benefit: 0.41s concurrent vs 0.70s sequential (1.7x faster)

It is the default isolation level for many relational databases *(MARIADB and MySQL being the exception)*, including PostgreSQL, Microsoft SQL Server, and Oracle

**Option 2: Explicit Locking**
- Use `LOCK TABLES data_table WRITE` (Test 2)
- Serializes writes, guaranteed consistency
- Performance: 0.44s (acceptable trade-off for safety)
- Concurrency benefit: 0.44s concurrent vs 0.70s sequential (1.6x faster)

**Option 3: Retry Logic (BALANCED)**
- Implement exponential backoff on deadlock detection (Test 6)
- Transient failures automatically resolved
- Performance: 0.48s (faster than explicit locking, graceful degradation)
- Concurrency benefit: 0.48s concurrent vs 0.70s sequential (1.5x faster)

**Option 7: Single-threaded Baseline**
- Run with 1 thread instead of 14 (Test 7)
- Eliminates concurrency entirely, zero deadlocks by design
- Performance: 0.05s per thread (0.70s total when multiplied by 14)
- Trade-off: No concurrency benefit; serialized execution

## How to Run

```bash
# Prerequisites
pip install mysql-connector-python

# Run test suite
python main.py
```

The test will:
1. Spin up a temporary MySQL 8.4 container
2. Execute 7 concurrent write tests with different strategies
3. Report pass/fail status, deadlock count, and timing

## Test Configuration

- **Concurrency:** 14 threads (Tests 1-6), 1 thread (Test 7 baseline)
- **Batch size:** 100 rows per write
- **Total operations:** 1,400 batch writes (14 threads × ~100 batches each)
- **Isolation levels:** REPEATABLE READ, READ COMMITTED
- **Locking strategies:** None, table-level, retry backoff, single-threaded
- **Baseline:** Single-threaded sequential execution (Test 7: 0.05s per thread = 0.70s total)

## GitHub Actions Workflow

Runs automatically on push to `main` or via manual workflow dispatch.

See `.github/workflows/mysql-test.yml` for CI/CD configuration.
