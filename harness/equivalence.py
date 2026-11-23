"""Equivalence check (dissertation Section 3.4.4).

Runs every program on every frozen test case and every random sequence and
accepts the programs only if (1) each output equals the expected output and
(2) the invariant checker finds no broken invariant.

Programs: Rust-Typed and Rust-Plain in the debug and release profiles, and the
Python program.  Usage:  python3 equivalence.py [--limit N]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import time

from checker import check_run
from model import read_csv, run

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")


def build() -> dict[str, list[str]]:
    for prof in ([], ["--release"]):
        subprocess.run(["cargo", "build", "-q", *prof], cwd=os.path.join(ROOT, "rust"), check=True)
    t = os.path.join(ROOT, "rust", "target")
    return {
        "rust_typed_debug": [os.path.join(t, "debug", "bank_typed_runner")],
        "rust_typed_release": [os.path.join(t, "release", "bank_typed_runner")],
        "rust_plain_debug": [os.path.join(t, "debug", "bank_plain_runner")],
        "rust_plain_release": [os.path.join(t, "release", "bank_plain_runner")],
        "python": ["python3", "-m", "bank.runner"],
    }


def run_prog(cmd: list[str], csv: str) -> tuple[int, list[str]]:
    p = subprocess.run(cmd + [csv], cwd=os.path.join(ROOT, "python"), capture_output=True, text=True)
    return p.returncode, p.stdout.splitlines()


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    progs = build()
    tests = sorted(glob.glob(os.path.join(DATA, "tests", "*.csv")))
    seqs = sorted(glob.glob(os.path.join(DATA, "sequences", "*.csv")))[: args.limit]
    summary = {}
    t0 = time.time()
    for name, cmd in progs.items():
        res = {"files": 0, "operations": 0, "crashes": 0, "output_differences": 0, "invariant_violations": 0, "first_problems": []}
        for f in tests + seqs:
            ops = read_csv(f)
            exp = (open(f.replace(".csv", ".expected.jsonl")).read().splitlines() if "/tests/" in f else run(ops))
            code, out = run_prog(cmd, f)
            res["files"] += 1; res["operations"] += len(ops)
            prob = None
            if code != 0:
                res["crashes"] += 1; prob = f"exit {code}"
            elif out != exp:
                res["output_differences"] += 1
                i = next(i for i, (a, b) in enumerate(zip(out + [""] * len(exp), exp)) if a != b)
                prob = f"first difference at step {i}"
            viol = check_run(ops, out) if code == 0 else []
            if viol:
                res["invariant_violations"] += len(viol); prob = (prob or "") + f" violations {viol[:2]}"
            if prob and len(res["first_problems"]) < 5:
                res["first_problems"].append(f"{os.path.basename(f)}: {prob}")
        res["accepted"] = res["crashes"] == res["output_differences"] == res["invariant_violations"] == 0
        summary[name] = res
        print(name, json.dumps(res))
    summary["_seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(DATA, "equivalence_report.json"), "w") as fh:
        json.dump(summary, fh, indent=1)


if __name__ == "__main__":
    main()
