import json
from pathlib import Path

from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("my_textual_app"))
CONFIG_FILE = CONFIG_DIR / "config.json"


# ── Theme management ────────────────────────────────────────────────────────


def load_theme() -> str:
    """Load saved theme or return default."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return data.get("theme", "textual-dark")  # or your default
        except Exception:
            pass
    return "textual-dark"  # fallback


def save_theme(theme_name: str) -> None:
    """Save the chosen theme."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"theme": theme_name}
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


# ── POS → chip class ────────────────────────────────────────────────────────


def token_class(pos: str) -> str:
    token = "token-chip-"
    match pos:
        case "動詞":
            return token + "verb"
        case "名詞":
            return token + "noun"
        case "形容詞" | "形状詞":
            return token + "adj"
        case "副詞":
            return token + "adv"
        case _:
            return token + "other"
