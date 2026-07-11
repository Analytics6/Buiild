from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.complaint_dataset import write_complaint_files


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate detailed complaint JSON dataset")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "complaints",
        help="Directory for complaint JSON files",
    )
    parser.add_argument("--count", type=int, default=200, help="Number of complaint files to create")
    parser.add_argument("--force", action="store_true", help="Overwrite existing complaint files")
    args = parser.parse_args()

    write_complaint_files(args.output_dir, count=args.count, force=True)
    print(f"Created {args.count} complaint files in {args.output_dir}")
