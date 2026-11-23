"""Defect runner (dissertation Sections 3.7.2 and 3.8.2).

For every mutant and defect scenario of one program, adds the single change to
a working copy, builds and tests it, and classifies the result:

  compile_time   the program does not build (Rust)
  static_check   mypy --strict reports an error (Python-Static only)
  testing        a frozen test or random sequence reveals it (crash, wrong
                 output, or broken invariant)
  not_caught     builds and passes every test and sequence

Rust mutants are built and tested in the debug and release profiles.
The frozen tests run first, then the 1,000 sequences, stopping at the first
detection.  Usage:  python3 run_defects.py rust_typed|rust_plain|python
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

from checker import check_run
from model import read_csv, run
from mutate import PROGRAMS, generate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORK = os.path.join(ROOT, "runs")  # working copies and build output (git-ignored)
DATA = os.path.join(ROOT, "data")
# -B: no bytecode cache. A cached .pyc is validated only by the source's mtime
# (whole seconds) and size, so two same-sized mutants of one file written within
# one second would otherwise run the earlier mutant (tests/test_run_defects.py).
PYTHON_RUNNER = [sys.executable, "-B", "-m", "bank.runner"]
CRATE = {"rust_typed": ("bank_typed", "bank_typed_runner"), "rust_plain": ("bank_plain", "bank_plain_runner")}


def load_data() -> list[tuple[str, list, list[str]]]:
    files = sorted(glob.glob(os.path.join(DATA, "tests", "*.csv"))) + sorted(glob.glob(os.path.join(DATA, "sequences", "*.csv")))
    out = []
    for f in files:
        ops = read_csv(f)
        exp = open(f.replace(".csv", ".expected.jsonl")).read().splitlines() if "/tests/" in f else run(ops)
        out.append((f, ops, exp))
    return out


def test(cmd: list[str], cwd: str, data) -> tuple[str, str]:
    """Return (class, detail)."""
    for f, ops, exp in data:
        try:
            p = subprocess.run(cmd + [f], cwd=cwd, capture_output=True, text=True, timeout=20,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        except subprocess.TimeoutExpired:
            return "testing", f"{os.path.basename(f)}: timeout"
        out = p.stdout.splitlines()
        name = os.path.basename(f)
        if p.returncode != 0:
            err = (p.stderr.strip().splitlines() or [""])[-1][:160]
            if "panicked" in p.stderr:
                err = next((l for l in p.stderr.splitlines() if "panicked" in l or "attempt to" in l), err)
                err = re.sub(r"thread '([^']*)' \(\d+\)", r"thread '\1'", err)[:160]  # drop the varying thread id
            return "testing", f"{name}: crash (exit {p.returncode}) {err}"
        viol = check_run(ops, out)
        diff = next((i for i, (a, b) in enumerate(zip(out, exp)) if a != b), None)
        if diff is None and len(out) != len(exp):
            diff = min(len(out), len(exp))
        if viol or diff is not None:
            parts = []
            if diff is not None:
                parts.append(f"wrong output at step {diff}")
            if viol:
                parts.append(f"invariants broken {sorted({x for _, v in viol for x in v})} first at step {viol[0][0]}")
            return "testing", f"{name}: " + "; ".join(parts)
    return "not_caught", f"passed all {len(data)} files"


def rust_codes(stderr: str) -> str:
    codes = sorted(set(re.findall(r"error\[(E\d{4})\]", stderr)))
    first = next((l.strip() for l in stderr.splitlines() if l.startswith("error")), "")
    return ",".join(codes) + " | " + first[:140]


def main(program: str) -> None:
    data = load_data()
    muts = generate(program)
    os.makedirs(WORK, exist_ok=True)
    rows = []
    t_start = time.time()
    if program.startswith("rust"):
        ws = os.path.join(WORK, program)
        shutil.rmtree(ws, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "rust"), ws, ignore=shutil.ignore_patterns("target"))
        env = dict(os.environ, CARGO_TARGET_DIR=os.path.join(WORK, f"target_{program}"))
        crate, binname = CRATE[program]
        for m in muts:
            rel = m.file.replace("rust/", "", 1)
            path = os.path.join(ws, rel)
            orig = open(path, encoding="utf-8").read()
            open(path, "w", encoding="utf-8").write(m.source)
            for prof in ("debug", "release"):
                t0 = time.time()
                args = ["cargo", "build", "-p", crate] + (["--release"] if prof == "release" else [])
                b = subprocess.run(args, cwd=ws, env=env, capture_output=True, text=True)
                warn = len(re.findall(r"^warning", b.stderr, flags=re.M))
                if b.returncode != 0:
                    cls, det = "compile_time", rust_codes(b.stderr)
                else:
                    exe = os.path.join(env["CARGO_TARGET_DIR"], prof, binname)
                    cls, det = test([exe], ws, data)
                rows.append(dict(program=program, configuration="Rust-Typed" if program == "rust_typed" else "Rust-Plain",
                                 profile=prof, mutant=m.id, kind=m.kind, operator=m.operator, line=m.line,
                                 before=m.before.replace("\n", " ")[:200], after=m.after.replace("\n", " ")[:200],
                                 result=cls, detail=det, build_warnings=warn, seconds=round(time.time() - t0, 2)))
                print(m.id, prof, cls, det[:90], flush=True)
            open(path, "w", encoding="utf-8").write(orig)
    else:
        ws = os.path.join(WORK, "python")
        shutil.rmtree(ws, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "python"), ws, ignore=shutil.ignore_patterns("__pycache__", ".mypy_cache"))
        for m in muts:
            path = os.path.join(ws, m.file.replace("python/", "", 1))
            orig = open(path, encoding="utf-8").read()
            open(path, "w", encoding="utf-8").write(m.source)
            t0 = time.time()
            my = subprocess.run(["mypy", "--strict", "--no-incremental", "bank"], cwd=ws, capture_output=True, text=True)
            my_err = my.returncode != 0
            my_det = next((l for l in my.stdout.splitlines() if ": error:" in l), "")[:200]
            cls, det = test(PYTHON_RUNNER, ws, data)
            base = dict(program=program, profile="", mutant=m.id, kind=m.kind, operator=m.operator, line=m.line,
                        before=m.before.replace("\n", " ")[:200], after=m.after.replace("\n", " ")[:200],
                        build_warnings=0, seconds=round(time.time() - t0, 2))
            rows.append(dict(base, configuration="Python-Runtime", result=cls, detail=det))
            rows.append(dict(base, configuration="Python-Static",
                             result="static_check" if my_err else cls, detail=my_det if my_err else det))
            print(m.id, "mypy" if my_err else "-", cls, det[:90], flush=True)
            open(path, "w", encoding="utf-8").write(orig)
    out = os.path.join(ROOT, "results", f"results_{program}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"done {program}: {len(rows)} rows in {round(time.time() - t_start)} s -> {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1])
