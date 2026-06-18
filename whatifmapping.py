from functools import lru_cache
from pathlib import Path
import json


@lru_cache(maxsize=1)
def whatif_mapping():
    data_path = Path(__file__).resolve().parent / "whatifmapping_data.json"
    if not data_path.exists():
        return {}
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)
