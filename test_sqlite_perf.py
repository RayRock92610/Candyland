import sqlite3
import time

conn = sqlite3.connect(':memory:')
conn.execute("CREATE TABLE recon (target TEXT, status_code INTEGER)")
conn.execute("BEGIN TRANSACTION")
for i in range(100000):
    conn.execute(f"INSERT INTO recon VALUES ('target{i}', 200)")
conn.execute("COMMIT")

start = time.time()
targets = [row[0] for row in conn.execute("SELECT target FROM recon WHERE status_code=200")]
print("Iter:", time.time() - start)

start = time.time()
targets = [row[0] for row in conn.execute("SELECT target FROM recon WHERE status_code=200").fetchall()]
print("Fetchall:", time.time() - start)

start = time.time()
targets = [row[0] for row in conn.cursor().execute("SELECT target FROM recon WHERE status_code=200").fetchall()]
print("Cursor Fetchall:", time.time() - start)
