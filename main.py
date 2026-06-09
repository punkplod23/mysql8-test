import mysql.connector
from mysql.connector import pooling
import threading
from datetime import datetime

db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "rootpassword",
    "database": "my_database"
}

def setup_database():
    conn = mysql.connector.connect(**{k: v for k, v in db_config.items() if k != 'database'})
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS my_database")
    cursor.execute("USE my_database")
    cursor.execute("DROP TABLE IF EXISTS data_table")
    # Added AUTO_INCREMENT to id
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
    # Note: With AUTO_INCREMENT, we don't insert 'id'
    for i in range(1, 1001):
        cursor.execute("INSERT INTO data_table (row_id) VALUES (%s)", (i,))
    conn.commit()
    cursor.close()
    conn.close()
    print("Schema created with AUTO_INCREMENT; 1000 rows seeded.")

pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="mypool", pool_size=10, **db_config)

def worker(thread_id, isolation_on, use_idiot_code):
    conn = pool.get_connection()
    cursor = conn.cursor()
    
    if isolation_on:
        # LLM suggested this as a workaround to avoid deadlocks, bbut it does not work. It just causes more deadlocks. I guess MySQL's locking is just really bad.
        #cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        # https://forums.mysql.com/read.php?22,65113,65113#msg-65113 an actual hack answer WTF
        cursor.execute("LOCK TABLES data_table WRITE")
        # Why this garbage hack works: https://dev.mysql.com/doc/refman/8.0/en/lock-tables.html#lock-tables-transaction-interaction
        # It acquires an exclusive lock on the entire table before any operations
        # All other threads block and wait for the lock to be released
        # No row-level deadlock can occur because only one thread accesses the table at a time
        # It's a blunt force solution: "if nobody else can touch it, nobody can fight over it"


    else:
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    try:
        # We iterate over row_id because 'id' is now managed by MySQL
        # Define multiple movement patterns
        patterns = [
            range(1, 1001, 100),       # Full Forward
            range(901, -1, -100),      # Full Backward
            range(1, 501, 100),        # First Half Forward
            range(901, 401, -100),     # Second Half Backward
            range(401, 701, 100),      # Middle Block Forward
            range(601, 301, -100),     # Middle Block Backward
            range(1, 1001, 200),       # Skip-Step Forward
            range(901, -1, -200),      # Skip-Step Backward
            range(201, 801, 100),      # Inner Segment Forward
            range(701, 101, -100),     # Inner Segment Backward
            range(1, 201, 100),        # Start Segment
            range(801, 1001, 100),     # End Segment
            range(1, 1001, 500),       # Large Jumps Forward
            range(901, -1, -500)       # Large Jumps Backward
        ]
        
        # Assign a pattern based on thread_id
        ranges = patterns[thread_id % len(patterns)]
        
        for start_id in ranges:
            batch = []
            for i in range(start_id, start_id + 100):
                batch.append(('val', 1, datetime.now(), i))
                # We do NOT include 'id' here.
                # We identify the row by 'row_id' (our unique key).
                batch.append(('val', 1, datetime.now(), i))
            
            # Slow so slow awful code
            if use_idiot_code:
                cursor.executemany("""
                    REPLACE INTO data_table (hash, job_id, date, row_id) 
                    VALUES (%s, %s, %s, %s)
                """, batch)
            else:
                cursor.executemany("""
                    INSERT INTO data_table (hash, job_id, date, row_id) 
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        hash = VALUES(hash)
                """, batch)
            
        conn.commit()
        print(f"Thread {thread_id}: Success")
        
    except mysql.connector.Error as err:
        if err.errno == 1213:
            print(f"!!! DEADLOCK DETECTED on Thread {thread_id} !!!")
        else:
            print(f"Thread {thread_id}: Error {err.errno}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def run_test(name, isolation_enabled):
    print(f"\n>>> Starting Test: {name}")
    threads = [threading.Thread(target=worker, args=(i, isolation_enabled)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()

if __name__ == "__main__":
    print("Testing MySQL 8 with multiple threads and different locking strategies...")
    setup_database()
    run_test("Test 1 (Table Locking ON )", True,False)
    run_test("Test 2 (Table Locking OFF)", False,False)
    run_test("Test 3 (Table Locking ON REPLACE INTO)", True,True)
    run_test("Test 4 (Table Locking OFF REPLACE INTO)", False,True)