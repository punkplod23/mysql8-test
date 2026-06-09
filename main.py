import mysql.connector
import threading
import time
import random
from datetime import datetime

db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "rootpassword",
    "database": "my_database"
}

# Thread-safe tracking
results_tracker = []
results_lock = threading.Lock()

def setup_database():
    conn = mysql.connector.connect(**{k: v for k, v in db_config.items() if k != 'database'})
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS my_database")
    cursor.execute("USE my_database")
    cursor.execute("DROP TABLE IF EXISTS data_table")
    cursor.execute("""
        CREATE TABLE data_table (
            id BIGINT NOT NULL AUTO_INCREMENT,
            hash VARCHAR(64) DEFAULT NULL,
            job_id BIGINT DEFAULT NULL,
            row_id BIGINT DEFAULT NULL,
            date TIMESTAMP NULL DEFAULT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY row_id_idx (row_id)
        ) ENGINE=InnoDB
    """)
    for i in range(1, 1001):
        cursor.execute("INSERT INTO data_table (row_id) VALUES (%s)", (i,))
    conn.commit()
    cursor.close()
    conn.close()
    print("Schema created with AUTO_INCREMENT; 1000 rows seeded.")

def worker(thread_id, lock_tables, use_idiot_code, isolation_level, max_retries):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    status = "SUCCESS"
    
    try:
        if lock_tables:
            cursor.execute("LOCK TABLES data_table WRITE")
        cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
        
        patterns = [
            range(1, 1001, 100), range(901, -1, -100), range(1, 501, 100),
            range(901, 401, -100), range(401, 701, 100), range(601, 301, -100),
            range(1, 1001, 200), range(901, -1, -200), range(201, 801, 100),
            range(701, 101, -100), range(1, 201, 100), range(801, 1001, 100),
            range(1, 1001, 500), range(901, -1, -500)
        ]
        ranges = patterns[thread_id % len(patterns)]
        
        for start_id in ranges:
            batch_success = False
            for attempt in range(max_retries):
                try:
                    batch = []
                    for i in range(start_id, start_id + 100):
                        batch.append(('val', 1, datetime.now(), i))
                    
                    if use_idiot_code:
                        cursor.executemany("REPLACE INTO data_table (hash, job_id, date, row_id) VALUES (%s, %s, %s, %s)", batch)
                    else:
                        cursor.executemany("INSERT INTO data_table (hash, job_id, date, row_id) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE hash = VALUES(hash)", batch)
                    
                    conn.commit()
                    batch_success = True
                    break 
                except mysql.connector.Error as err:
                    conn.rollback()
                    if err.errno in (1213, 1205) and attempt < max_retries - 1:
                        time.sleep((0.1 * (2 ** attempt)) + (random.random() * 0.1))
                    else:
                        raise err
            if not batch_success:
                status = "FAILED"
                break
        
    except mysql.connector.Error as err:
        status = "FAILED"
        if err.errno == 1213:
            print(f"!!! DEADLOCK DETECTED on thread {thread_id} !!!")
    finally:
        if lock_tables:
            cursor.execute("UNLOCK TABLES")
        cursor.close()
        conn.close()
        with results_lock:
            results_tracker.append(status)

def run_test(name, lock_tables, use_idiot_code, isolation_level, max_retries):
    global results_tracker
    results_tracker = []
    print(f"\n>>> Starting Test: {name}")
    
    threads = [threading.Thread(target=worker, args=(i, lock_tables, use_idiot_code, isolation_level, max_retries)) for i in range(14)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    failed_count = results_tracker.count("FAILED")
    return failed_count

if __name__ == "__main__":
    print("="*70)
    print("MYSQL CONCURRENCY AND DEADLOCK TEST SUITE")
    print("="*70)
    print("Objective: Evaluate performance and reliability of 14 concurrent ")
    print("threads performing batch updates (100 rows/batch) on a shared table.")
    print("\nMetrics tracked:")
    print(" - Performance: Wall-clock time taken to complete 1,400 batch writes.")
    print(" - Reliability: Deadlock frequency and transaction success rates.")
    print("="*70)
    print("Strategies tested:")
    print(" 1. Standard (No Locks, REPEATABLE READ)")
    print(" 2. Table-Level Locking (Exclusive write access)")
    print(" 3. Relaxed Consistency (READ COMMITTED)")
    print(" 4. Destructive Writes (REPLACE INTO vs INSERT IGNORE)")
    print(" 5. Resilient Retries (Exponential backoff on conflict)")
    print("="*70)
    setup_database()
    tests = [
        ("Test 1 (NORMAL RUN)", False, False, "REPEATABLE READ", 1),
        ("Test 2 (TABLE LEVEL LOCKING)", True, False, "REPEATABLE READ", 1),
        ("Test 3 (ISOLATION LEVEL READ COMMITTED)", False, False, "READ COMMITTED", 1),
        ("Test 4 (REPLACE INTO, LOCK OFF)", False, True, "REPEATABLE READ", 1),
        ("Test 5 (REPLACE INTO, LOCK ON)", True, True, "REPEATABLE READ", 1),
        ("Test 6 (NORMAL RUN WITH 5 Retries)", False, False, "REPEATABLE READ", 5)
    ]
    
    results = []
    for name, lock, idiot, iso, retries in tests:
        start_time = time.time()
        fails = run_test(name, lock, idiot, iso, retries)
        duration = time.time() - start_time
        results.append((name, duration, fails))
        print(f"--- {name} finished in {duration:.2f} seconds ---")

    print("\n" + "="*70)
    print(f"{'TEST NAME':<35} | {'TIME':<8} | {'STATUS'}")
    print("-" * 70)
    for name, dur, fails in results:
        status = "PASSED" if fails == 0 else f"FAILED ({fails} deadlocks)"
        print(f"{name:<35} | {dur:>6.2f}s | {status}")
    print("="*70)