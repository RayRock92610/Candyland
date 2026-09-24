import requests
import time
from concurrent.futures import ThreadPoolExecutor

urls = ["http://example.com" for _ in range(20)]

def fetch_stream(url, session):
    try:
        with session.get(url, stream=True) as r:
            pass
    except:
        pass

def fetch_nostream(url, session):
    try:
        with session.get(url, stream=False) as r:
            pass
    except:
        pass

s = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
s.mount("http://", adapter)

start = time.time()
for url in urls:
    fetch_stream(url, s)
print("Stream sequential:", time.time() - start)

s = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
s.mount("http://", adapter)
start = time.time()
for url in urls:
    fetch_nostream(url, s)
print("No stream sequential:", time.time() - start)
