"""Generate adapters without copying credentials or private endpoints into source."""

import sys
from pathlib import Path


def auto_generate_llm_call():
    code_dir = Path(__file__).resolve().parents[1]
    if str(code_dir) not in sys.path:
        sys.path.insert(0, str(code_dir))
    from pipeline.model_resolver import _ensure_model_file, list_available_models

    models = list_available_models()
    for model_info in models:
        _ensure_model_file(model_info)
    print(f"Generated {len(models)} adapter(s). Configuration is loaded at runtime; no API calls made.")


if __name__ == "__main__":
    auto_generate_llm_call()
