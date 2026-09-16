"""Converts a local checkout of the Foundry PF2e packs into chunk files.

    git clone --depth 1 --filter=blob:none --sparse \\
        https://github.com/foundryvtt/pf2e.git
    cd pf2e && git sparse-checkout set packs

    uv run python -m app.foundry_cli --packs <checkout>/packs/pf2e

Minutes rather than the crawler's hours, because nothing is fetched: the
work is reading JSON off disk. Re-running is safe — ids are derived from the
source path, so the index upserts over the same rows.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

from app.core.config import settings
from app.foundry import DEFAULT_REF, convert_tree

_log = logging.getLogger("foundry")


def _checkout_commit(packs_root: Path) -> str:
    """The commit the packs were read from, for citations that keep working.

    A branch name in a source link rots: the branch moves on and the link
    then points at content the answer was not based on. Falls back to the
    branch when the directory is not a git checkout.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(packs_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return DEFAULT_REF
    return result.stdout.strip() or DEFAULT_REF


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Foundry VTT PF2e packs into chunk .jsonl files."
    )
    parser.add_argument(
        "--packs",
        required=True,
        help="Path to packs/pf2e inside a foundryvtt/pf2e checkout",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write the .jsonl files (default: the configured chunk directory)",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Git ref to cite in source links (default: the checkout's own commit)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    packs_root = Path(args.packs)
    if not packs_root.is_dir():
        raise SystemExit(f"No such directory: {packs_root}")

    output_dir = Path(args.output_dir or settings.output_dir)
    ref = args.ref or _checkout_commit(packs_root)
    written = convert_tree(packs_root, output_dir, ref=ref)

    print(f"source: foundryvtt/pf2e @ {ref}")
    total = sum(written.values())
    for pack, count in sorted(written.items(), key=lambda item: -item[1]):
        print(f"  {pack:<40} {count:>6}")
    print(f"\n{total} chunks from {len(written)} packs -> {output_dir}")


if __name__ == "__main__":
    main()
