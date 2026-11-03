# docs/api/snippets/verify_webhook.py (Python ≥ 3.8, run by the tests via python3)
import hashlib, hmac, time
def verify_storeshot_signature(raw_body: bytes, header: str, secret: str, tolerance=300, now=None) -> bool:
    items = [p.strip().split("=", 1) for p in header.split(",") if "=" in p]
    ts = [v for k, v in items if k == "t"]
    if len(ts) != 1 or not ts[0].isdigit() or abs((now or time.time()) - int(ts[0])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), ts[0].encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, v) for k, v in items if k == "v1")
