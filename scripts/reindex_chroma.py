from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.chroma_store import get_chroma_store, load_documents_from_json
from backend.app.config import get_settings


def main() -> None:
    settings = get_settings()
    docs = load_documents_from_json(settings.data_dir)
    count = get_chroma_store().index_documents(docs, replace=True)
    print(f"Reindexed {count} documents from {settings.data_dir}")


if __name__ == "__main__":
    main()
