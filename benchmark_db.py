import sqlite3
import time

db = sqlite3.connect('kessel_RECON_test.db')
db.execute("CREATE TABLE recon (id INTEGER PRIMARY KEY, target TEXT, status_code INTEGER)")
db.execute("BEGIN TRANSACTION")
for i in range(100000):
    status = 200 if i % 10 == 0 else 404
    db.execute(f"INSERT INTO recon (target, status_code) VALUES ('target{i}', {status})")
db.execute("COMMIT")

start = time.time()
db.execute("SELECT target FROM recon WHERE status_code=200").fetchall()
print("Without index:", time.time() - start)

db.execute("CREATE INDEX idx_status ON recon(status_code)")
start = time.time()
db.execute("SELECT target FROM recon WHERE status_code=200").fetchall()
print("With index:", time.time() - start)
