import time
import requests

paths = ["/.git/config", "/.env", "/robots.txt", "/.vscode/settings.json"]
target = "example.com"

start = time.time()
for p in paths:
    try:
        requests.get(f"https://{target}{p}", timeout=4, allow_redirects=False)
    except:
        pass
print("Without Session:", time.time() - start)

start = time.time()
with requests.Session() as s:
    for p in paths:
        try:
            s.get(f"https://{target}{p}", timeout=4, allow_redirects=False)
        except:
            pass
print("With Session:", time.time() - start)
