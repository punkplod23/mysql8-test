<<<<<<< HEAD
Testing some INNODB stratergies
=======
# MySQL InnoDB Concurrency & Deadlock Test Suite

Testing various strategies to handle concurrent writes and deadlock prevention in MySQL 8.4 with InnoDB.

## Latest Test Run

**Job:** [GitHub Actions Run #80446459447](https://github.com/punkplod23/mysql8-test/actions/runs/27241628045/job/80446459447)

### Results Summary

| Test | Strategy | Status | Deadlocks | Duration |
|------|----------|--------|-----------|----------|
| Test 1 | Standard (REPEATABLE READ, no locks) | ❌ FAILED | 8 | 0.32s |
| Test 2 | Table-Level Locking (WRITE) | ✅ PASSED | 0 | 0.38s |
| Test 3 | READ COMMITTED isolation | ✅ PASSED | 0 | 0.33s |
| Test 4 | REPLACE INTO (no locks) | ❌ FAILED | 8 | 1.12s |
| Test 5 | REPLACE INTO + table locks | ✅ PASSED | 0 | 2.39s |
| Test 6 | REPEATABLE READ + retry logic | ✅ PASSED | 0 | 0.66s |

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
- Performance: 0.33s (same speed, 100% reliable)

It is the default isolation level for many relational databases *(NOT DESIGNED BY ORACLE)*, including PostgreSQL, Microsoft SQL Server, and Oracle

**Option 2: Explicit Locking**
- Use `LOCK TABLES data_table WRITE` (Test 2)
- Serializes writes, guaranteed consistency
- Performance: 0.38-2.39s (6x slower, trade-off acceptable for safety)

**Option 3: Retry Logic (BALANCED)**
- Implement exponential backoff on deadlock detection (Test 6)
- Transient failures automatically resolved
- Performance: 0.66s (faster than explicit locking, graceful degradation)

## How to Run

```bash
# Prerequisites
pip install mysql-connector-python

# Run test suite
python main.py
```

The test will:
1. Spin up a temporary MySQL 8.4 container
2. Execute 6 concurrent write tests with different strategies
3. Report pass/fail status, deadlock count, and timing

## Test Configuration

- **Concurrency:** 14 threads
- **Batch size:** 100 rows per write
- **Total operations:** 1,400 batch writes (14 threads × ~100 batches each)
- **Isolation levels:** REPEATABLE READ, READ COMMITTED
- **Locking strategies:** None, table-level, retry backoff

## GitHub Actions Workflow

Runs automatically on push to `main` or via manual workflow dispatch.

See `.github/workflows/mysql-test.yml` for CI/CD configuration.
>>>>>>> 500a6bef9958a3a41b365cb1e711cbc36caa3bcc
