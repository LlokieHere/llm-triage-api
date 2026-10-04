import json
import os
import urllib.request
import urllib.error

URL = "http://127.0.0.1:8000/triage"
HERE = os.path.dirname(__file__)

with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
    cases = json.load(f)

passed = 0
failures = []

for c in cases:
    req = urllib.request.Request(
        URL,
        data=json.dumps({"text": c["text"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            got = json.loads(r.read())["category"]
    except urllib.error.HTTPError as e:
        got = f"HTTP {e.code}"
    except Exception as e:
        got = f"ERROR {e}"

    if got == c["expected"]:
        passed += 1
    else:
        failures.append((c["text"], c["expected"], got))

print(f"Score: {passed}/{len(cases)} = {passed / len(cases) * 100:.0f}%")
for text, expected, got in failures:
    print(f"FAIL: {text!r} expected={expected} got={got}")