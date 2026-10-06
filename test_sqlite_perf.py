import sqlite3
import time

conn = sqlite3.connect(":memory:")
conn.execute("""
CREATE TABLE queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL,
    status TEXT NOT NULL
);
""")

# Insert 100,000 completed
conn.execute("BEGIN TRANSACTION;")
for _ in range(100000):
    conn.execute("INSERT INTO queue (recipient, status) VALUES ('Sentinel', 'COMPLETED')")
conn.execute("COMMIT;")

start = time.time()
for _ in range(100):
    conn.execute("SELECT id FROM queue WHERE recipient = 'Sentinel' AND status = 'PENDING' ORDER BY id ASC LIMIT 1").fetchone()
print("Without index:", time.time() - start)

conn.execute("CREATE INDEX idx_queue_rec_stat ON queue(recipient, status);")
start = time.time()
for _ in range(100):
    conn.execute("SELECT id FROM queue WHERE recipient = 'Sentinel' AND status = 'PENDING' ORDER BY id ASC LIMIT 1").fetchone()
print("With index:", time.time() - start)
