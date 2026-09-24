"""Determinism check: regenerate a mode with the same seed and compare every file byte for byte.

Usage (inside WSL, repo root, venv active):
    python -m data_generator.determinism_check --mode full --tmp ~/det_check
    python -m data_generator.determinism_check --mode sample --tmp /tmp/det_check --control-seed 43

The reference is the run already on disk: raw_data/<mode>/ with its checksums in
data_generator/manifests/<mode>/file_checksums.json. The check regenerates into --tmp
(kept inside the WSL disk), compares SHA-256 checksums of all files and the injection
manifest, then deletes the temporary copy. With --control-seed it also generates once with a
different seed and confirms the output DOES change (so the check is not trivially true).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from .generate import PROJECT_ROOT, generate


def _compare(ref: dict, new: dict) -> tuple[int, list]:
    """Return (number of identical files, list of differences)."""
    diffs = []
    for name in sorted(set(ref) | set(new)):
        if name not in new:
            diffs.append(f"missing in rerun: {name}")
        elif name not in ref:
            diffs.append(f"extra in rerun: {name}")
        elif ref[name]["sha256"] != new[name]["sha256"]:
            diffs.append(f"content differs: {name}")
    return len(set(ref) & set(new)) - sum(d.startswith("content") for d in diffs), diffs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["full", "sample", "hidden_like"])
    ap.add_argument("--tmp", type=Path, required=True, help="scratch folder inside the WSL disk")
    ap.add_argument("--control-seed", type=int, help="also run with this seed and expect different output")
    args = ap.parse_args()

    mdir = PROJECT_ROOT / "data_generator" / "manifests" / args.mode
    ref_files = json.loads((mdir / "file_checksums.json").read_text())
    ref_manifest = json.loads((mdir / "injection_manifest.json").read_text())
    tmp = args.tmp.expanduser().resolve()
    ok = True
    try:
        generate(args.mode, tmp / "data", tmp / "manifest")
        new_files = json.loads((tmp / "manifest" / "file_checksums.json").read_text())
        new_manifest = json.loads((tmp / "manifest" / "injection_manifest.json").read_text())
        same, diffs = _compare(ref_files, new_files)
        total_bytes = sum(f["bytes"] for f in ref_files.values())
        print(f"\nSame seed: {same}/{len(ref_files)} files identical (SHA-256), {total_bytes / 1e6:,.1f} MB compared")
        for d in diffs[:20]:
            print("  ", d)
        manifest_same = new_manifest == ref_manifest
        print(f"Injection manifest identical: {manifest_same}")
        ok = not diffs and manifest_same

        if args.control_seed is not None:
            generate(args.mode, tmp / "control", tmp / "control_manifest", seed=args.control_seed)
            ctrl = json.loads((tmp / "control_manifest" / "file_checksums.json").read_text())
            _, cdiffs = _compare(ref_files, ctrl)
            changed = sum(d.startswith("content") for d in cdiffs)
            print(f"Control seed {args.control_seed}: {changed}/{len(ref_files)} files differ "
                  f"(event tables must change; the network and passenger registry depend only on network_seed)")
            ok = ok and changed > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nDETERMINISM: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
