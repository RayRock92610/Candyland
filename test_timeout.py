import requests
import time

s = requests.Session()
paths = ["/1", "/2", "/3", "/4"]
start = time.time()
for p in paths:
    try:
        s.get("https://10.255.255.1" + p, timeout=1)
    except Exception as e:
        pass
print("Without early break:", time.time() - start)

start = time.time()
for p in paths:
    try:
        s.get("https://10.255.255.1" + p, timeout=1)
    except requests.exceptions.RequestException:
        break
print("With early break:", time.time() - start)
