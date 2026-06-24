from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path


def run(run_dir: Path) -> None:
    files = []
    for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
        if path.name in {"output_manifest.json", "output_manifest.csv"}:
            continue
        rel = path.relative_to(run_dir).as_posix()
        files.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (run_dir / "logs" / "output_manifest.json").write_text(
        json.dumps({"run_dir": str(run_dir), "files": files}, indent=2),
        encoding="utf-8",
    )
    import pandas as pd

    pd.DataFrame(files).to_csv(run_dir / "logs" / "output_manifest.csv", index=False)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args()
    run(args.run_dir)


if __name__ == "__main__":
    main()
