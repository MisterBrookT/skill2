from __future__ import annotations

import argparse
from pathlib import Path

from skill2.bundle import check_skill_runtimes, sync_skill_runtimes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync skill2 Skill runtime bundles from src/")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if generated runtimes are stale; print stale paths",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repository root (default: parent of tools/)",
    )
    args = parser.parse_args(argv)

    repo_root = (args.repo_root or Path(__file__).resolve().parents[1]).resolve()

    if args.check:
        stale = check_skill_runtimes(repo_root)
        if stale:
            for path in stale:
                print(path)
            return 1
        return 0

    written = sync_skill_runtimes(repo_root)
    for path in written:
        try:
            print(path.relative_to(repo_root))
        except ValueError:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
