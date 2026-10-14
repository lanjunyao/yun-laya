"""Download the pinned multilingual checkpoint outside the repository."""
from pathlib import Path
from huggingface_hub import snapshot_download

DEST = Path.home() / ".local/share/yun-laya/models"
if __name__ == "__main__":
    snapshot_download(repo_id="convaiinnovations/laya",
        revision="1c5edc17a7acd8701df6fc341c0d179f1c62c982",
        allow_patterns=["multilingual/*"], local_dir=str(DEST))
    model = DEST / "multilingual"
    required = ["model.safetensors", "rl_agent_config.json", "encoder/config.json", "tokenizer/tokenizer.json"]
    if not all((model / item).is_file() for item in required):
        raise SystemExit("Model is incomplete; retry the download.")
    print(f"Downloaded. Save this line in ~/.config/yun-laya/env:\nLAYA_MODEL_DIR={model}")
