import time
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

paths = ["/.git/config", "/.env", "/robots.txt", "/.vscode/settings.json"]
target = "example.com"

# Without session
start = time.time()
for p in paths:
    try:
        r = requests.get(f"https://{target}{p}", timeout=4, verify=False, allow_redirects=False)
    except:
        pass
time_without = time.time() - start
print(f"Without session: {time_without:.2f}s")

# With session
start = time.time()
with requests.Session() as session:
    for p in paths:
        try:
            r = session.get(f"https://{target}{p}", timeout=4, verify=False, allow_redirects=False)
        except:
            pass
time_with = time.time() - start
print(f"With session: {time_with:.2f}s")
