import requests
import time
from kessel import Kessel

k = Kessel()

def test_audit_node_optimized(target, session=None):
    valid_hits = []
    local_session = False
    if session is None:
        session = requests.Session()
        local_session = True
    try:
        for p in k.paths:
            url = f"https://{target}{p}"
            try:
                with session.get(url, headers=k.headers, timeout=4, verify=True, allow_redirects=False) as r:
                    if r.status_code == 200 and k.is_truth(r):
                        size = len(r.content)
                        valid_hits.append((target, p, size))
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                break
            except Exception:
                pass
    finally:
        if local_session:
            session.close()
    return valid_hits

start = time.time()
test_audit_node_optimized("10.255.255.1")
print("Time taken optimized:", time.time() - start)
