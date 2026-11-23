"""Summarise the experiment for Chapter Four (dissertation Section 3.9).

Reads results/results_<program>.csv and the source trees, and writes:

  results/summary.md            all tables below, as Markdown
  results/scenario_matrix.csv   DS x configuration detection stage   (RQ1, RQ2)
  results/operator_summary.csv  operator x configuration x stage     (RQ2)
  results/enforcement_loc.csv   tagged enforcement lines per invariant and
                                file, and code lines per layer        (RQ3)
  results/environment.json      tool versions used for the run        (Section 3.3)

Usage:  python3 summarise.py
"""
from __future__ import annotations

import csv
import json
import os
import platform
import re
import subprocess
from collections import Counter, defaultdict

from mutate import PROGRAMS, SCENARIOS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "results")
CONFIGS = ["Rust-Typed", "Rust-Plain", "Python-Runtime", "Python-Static"]
STAGES = ["compile_time", "static_check", "testing", "not_caught"]
SHORT = {"compile_time": "compile", "static_check": "mypy", "testing": "test", "not_caught": "MISSED"}
INVARIANTS = ["I1", "I2", "I3", "I4", "I5"]
LAYERS = ["types", "domain", "repository", "services", "runner"]


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in PROGRAMS:
        path = os.path.join(RES, f"results_{p}.csv")
        if os.path.exists(path):
            rows += list(csv.DictReader(open(path, encoding="utf-8")))
    return rows


def stage_of(rows: list[dict[str, str]]) -> str:
    """Combine the debug/release rows of one mutant into one label."""
    by_prof = {r["profile"] or "-": r["result"] for r in rows}
    vals = set(by_prof.values())
    if len(vals) == 1:
        return SHORT[vals.pop()]
    return " / ".join(f"{SHORT[v]} ({k})" for k, v in sorted(by_prof.items()))


def scenario_matrix(rows: list[dict[str, str]]) -> list[list[str]]:
    grp: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        if r["kind"] == "scenario":
            grp[(r["operator"], r["configuration"])].append(r)
    out = []
    for ds, (title, inv, origin, _) in SCENARIOS.items():
        out.append([ds, title, inv, origin] + [stage_of(grp[(ds, c)]) if grp.get((ds, c)) else "n/a" for c in CONFIGS])
    return out


def operator_summary(rows: list[dict[str, str]]) -> list[list[str]]:
    # One outcome per mutant and configuration: the release profile is reported
    # separately only when it differs, so count the debug row (or the only row).
    cnt: Counter[tuple[str, str, str]] = Counter()
    for r in rows:
        if r["kind"] != "operator" or r["profile"] == "release":
            continue
        cnt[(r["operator"], r["configuration"], r["result"])] += 1
    ops = sorted({k[0] for k in cnt})
    out = []
    for op in ops + ["TOTAL"]:
        line = [op]
        for c in CONFIGS:
            vals = [sum(n for (o, cc, s), n in cnt.items() if (o == op or op == "TOTAL") and cc == c and s == st)
                    for st in STAGES]
            line.append("/".join(str(v) for v in vals))
        out.append(line)
    return out


def profile_differences(rows: list[dict[str, str]]) -> list[list[str]]:
    by: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for r in rows:
        if r["profile"]:
            by[(r["configuration"], r["mutant"])][r["profile"]] = r["result"] + " | " + r["detail"][:70]
    return [[c, m, v.get("debug", ""), v.get("release", "")] for (c, m), v in sorted(by.items())
            if v.get("debug", "").split(" |")[0] != v.get("release", "").split(" |")[0]]


def source_files(program: str) -> list[str]:
    base = os.path.join(ROOT, os.path.dirname(PROGRAMS[program]["service"]), "..")
    base = os.path.normpath(base)
    ext = ".rs" if PROGRAMS[program]["lang"] == "rust" else ".py"
    out = []
    for d, _, fs in os.walk(base):
        if "__pycache__" in d:
            continue
        out += [os.path.join(d, f) for f in fs if f.endswith(ext)]
    return sorted(out)


def layer_of(path: str) -> str:
    for layer in LAYERS[:-1]:
        if f"/{layer}/" in path:
            return layer
    return "runner" if os.path.basename(path) in ("main.rs", "runner.py") else "crate root"


def is_code_line(line: str, lang: str) -> bool:
    t = line.strip()
    if not t:
        return False
    if lang == "rust":
        return not t.startswith("//")
    return not t.startswith("#") and not (t.startswith('"""') and t.endswith('"""'))


def enforcement(program: str) -> tuple[dict[str, int], dict[str, set[str]], dict[str, int], int]:
    lang = PROGRAMS[program]["lang"]
    per_inv: Counter[str] = Counter()
    where: dict[str, set[str]] = defaultdict(set)
    per_layer: Counter[str] = Counter()
    tagged = 0
    for f in source_files(program):
        rel = os.path.relpath(f, ROOT)
        for ln in open(f, encoding="utf-8"):
            if is_code_line(ln, lang):
                per_layer[layer_of(f)] += 1
            m = re.search(r"\[ENF:([I0-9,]+)\]", ln)
            if m:
                tagged += 1
                for inv in m.group(1).split(","):
                    per_inv[inv] += 1
                    where[inv].add(os.path.basename(rel))
    return dict(per_inv), where, dict(per_layer), tagged


def environment() -> dict[str, str]:
    def v(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip().splitlines()[0]
        except (OSError, IndexError):
            return "unavailable"
    return {"rustc": v(["rustc", "--version"]), "cargo": v(["cargo", "--version"]),
            "python": platform.python_version(), "mypy": v(["mypy", "--version"]),
            "os": f"{platform.system()} {platform.release()}"}


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_csv(name: str, header: list[str], rows: list[list[str]]) -> None:
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rows = load_rows()
    md = ["# Experiment summary", ""]

    env = environment()
    json.dump(env, open(os.path.join(RES, "environment.json"), "w"), indent=1)
    md += ["## Environment", "", md_table(["tool", "version"], [[k, v] for k, v in env.items()]), ""]

    h = ["DS", "scenario", "invariant", "origin"] + CONFIGS
    sm = scenario_matrix(rows)
    write_csv("scenario_matrix.csv", h, sm)
    md += ["## Defect scenarios: detection stage (RQ1, RQ2)", "",
           "compile = rejected by rustc; mypy = rejected by mypy --strict; test = revealed by the frozen tests or "
           "random sequences; MISSED = passed every test.", "", md_table(h, sm), ""]

    h = ["operator"] + [f"{c} (compile/mypy/test/missed)" for c in CONFIGS]
    os_ = operator_summary(rows)
    write_csv("operator_summary.csv", h, os_)
    md += ["## Operator mutants: outcomes (debug profile for Rust)", "", md_table(h, os_), ""]

    pd = profile_differences(rows)
    md += ["## Mutants whose outcome differs between debug and release", ""]
    md += [md_table(["configuration", "mutant", "debug", "release"], pd) if pd else "None.", ""]

    missed = [[r["configuration"], r["mutant"], r["profile"], r["before"][:70], r["after"][:70]]
              for r in rows if r["result"] == "not_caught"]
    md += ["## Mutants not caught", ""]
    md += [md_table(["configuration", "mutant", "profile", "before", "after"], missed) if missed else "None.", ""]

    loc_rows, inv_rows = [], []
    for p in PROGRAMS:
        per_inv, _, per_layer, tagged = enforcement(p)
        inv_rows.append([p] + [str(per_inv.get(i, 0)) for i in INVARIANTS] + [str(tagged)])
        loc_rows.append([p] + [str(per_layer.get(layer, 0)) for layer in ["crate root"] + LAYERS]
                        + [str(sum(per_layer.values()))])
    h_inv = ["program"] + INVARIANTS + ["tagged lines"]
    h_loc = ["program", "crate root", *LAYERS, "total"]
    write_csv("enforcement_loc.csv", h_inv, inv_rows)
    md += ["## Enforcement code volume (RQ3)", "",
           "Lines carrying an [ENF:Ix] tag (SPEC Section 5). A line tagged with two invariants counts once per invariant "
           "and once in the total.", "", md_table(h_inv, inv_rows), "",
           "### Where each invariant is enforced (files containing tagged lines)", ""]
    for p in PROGRAMS:
        _, where, _, _ = enforcement(p)
        md.append(f"- **{p}**: " + "; ".join(f"{i}: {', '.join(sorted(where[i]))}" for i in INVARIANTS if i in where))
    md += ["", "### Code lines per layer (non-blank, non-comment)", "", md_table(h_loc, loc_rows), ""]

    open(os.path.join(RES, "summary.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
