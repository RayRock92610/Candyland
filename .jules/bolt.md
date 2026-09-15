## 2024-03-24 - [requests.Session for TCP Connection Pooling]
**Learning:** Using `requests.get` in a loop to the same host results in setting up a new TCP connection and TLS handshake for every request, which is incredibly slow for recon tools scanning multiple paths on the same target.
**Action:** Always use `requests.Session()` to pool connections and reuse TLS when making multiple requests to the same target domain in recon tools, resulting in ~50%+ speedups.
