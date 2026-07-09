from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.complaint_rag import build_demo_dataset


if __name__ == "__main__":
    output_dir = Path(__file__).resolve().parents[1] / "data" / "complaints"
    build_demo_dataset(output_dir, count=200)
    print(f"Created complaint dataset in {output_dir}")
