from kessel import Kessel
import time

start = time.time()
Kessel().audit_node("10.255.255.1")
print("Time taken:", time.time() - start)
