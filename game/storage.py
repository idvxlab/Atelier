import json
from pathlib import Path


def load_high_score(path):
    file_path = Path(path)
    if not file_path.exists():
        return 0
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return int(data.get("high_score", 0))
    except (ValueError, OSError, json.JSONDecodeError):
        return 0


def save_high_score(path, score):
    file_path = Path(path)
    payload = {"high_score": int(score)}
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
