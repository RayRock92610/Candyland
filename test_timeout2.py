import requests
try:
    requests.get("https://10.255.255.1", timeout=1)
except requests.exceptions.ConnectTimeout:
    print("ConnectTimeout!")
except Exception as e:
    print("Other:", type(e))
