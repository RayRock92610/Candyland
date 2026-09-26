import requests
import time

s = requests.Session()
headers = {"User-Agent": "test"}
req = requests.Request('GET', 'http://example.com', headers=headers)
start = time.time()
for _ in range(10000):
    s.prepare_request(req)
print("Without session headers:", time.time() - start)

s = requests.Session()
s.headers.update(headers)
req2 = requests.Request('GET', 'http://example.com')
start = time.time()
for _ in range(10000):
    s.prepare_request(req2)
print("With session headers:", time.time() - start)
