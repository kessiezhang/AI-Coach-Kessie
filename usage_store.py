"""Track prompt usage per user per day. Limit: 10 prompts per user per day."""
import json
from datetime import date
from pathlib import Path

USAGE_FILE = Path(__file__).parent / "prompt_usage.json"
DAILY_LIMIT = 10


def _today() -> str:
    return date.today().isoformat()


def _load():
    if not USAGE_FILE.exists():
        return {}
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_usage(email: str) -> tuple[int, bool]:
    """Returns (prompts_used_today, can_send)."""
    data = _load()
    user = data.get(email, {})
    if isinstance(user, dict) and "prompts_used" in user:
        # Migrate old format: {"prompts_used": N} -> {date: N}
        user = {_today(): user.get("prompts_used", 0)}
    used_today = user.get(_today(), 0)
    can_send = used_today < DAILY_LIMIT
    return used_today, can_send


def increment_usage(email: str):
    data = _load()
    if email not in data:
        data[email] = {}
    user = data[email]
    if isinstance(user, dict) and "prompts_used" in user and _today() not in user:
        # Migrate old format
        user = {_today(): user.get("prompts_used", 0)}
    today = _today()
    user[today] = user.get(today, 0) + 1
    data[email] = user
    _save(data)
