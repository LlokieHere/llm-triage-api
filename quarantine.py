import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "quarantine.jsonl")

def quarantine(user_text, error, prompt_version):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "input": user_text,
        "error": str(error),
        "prompt_version": prompt_version,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")