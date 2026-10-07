"""Download public model weights once; inference subsequently stays local."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from huggingface_hub import snapshot_download
from services.local_llm import model_directory, model_name


if __name__ == '__main__':
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    directory = model_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = snapshot_download(
        repo_id=model_name(), local_dir=str(directory), token=False,
        allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja'],
    )
    print(f'Local model downloaded to {path}')
