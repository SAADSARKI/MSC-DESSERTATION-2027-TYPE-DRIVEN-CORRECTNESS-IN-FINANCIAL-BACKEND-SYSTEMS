"""Validation of the generated data (dissertation Section 3.8.1).

Checks that the data does what the methodology promises and writes
data/validation_report.json. Run after generate.py:  python3 validate_data.py
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import subprocess
import sys
import tempfile
from collections import Counter

from checker import check_run
from model import M, Op, read_csv, run

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))


def reproducibility() -> dict[str, object]:
    base = json.load(open(os.path.join(DATA, "manifest.json")))
    res: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([sys.executable, os.path.join(HERE, "generate.py"), "--seed", str(base["seed"]), "--out", t],
                       check=True, capture_output=True)
        same = json.load(open(os.path.join(t, "manifest.json")))["files"] == base["files"]
        res["same_seed_identical_files"] = same
    with tempfile.TemporaryDirectory() as t:
        subprocess.run([sys.executable, os.path.join(HERE, "generate.py"), "--seed", str(base["seed"] + 1), "--out", t],
                       check=True, capture_output=True)
        other = json.load(open(os.path.join(t, "manifest.json")))["files"]
        seqs = [k for k in base["files"] if k.startswith("sequences")]
        res["different_seed_sequences_changed"] = sum(other[k] != base["files"][k] for k in seqs)
        res["sequences_total"] = len(seqs)
    return res


def sequences() -> dict[str, object]:
    files = sorted(glob.glob(os.path.join(DATA, "sequences", "*.csv")))
    lengths, accounts, inv_share = [], [], []
    ops_c, err_c = Counter(), Counter()
    self_transfers = violations = 0
    cov = Counter()
    for f in files:
        ops = read_csv(f)
        lines = run(ops)
        lengths.append(len(ops))
        last = json.loads(lines[-1])
        accounts.append(len(last["accounts"]))
        errs = 0
        prev_bal: dict[str, int] = {}
        for o, ln in zip(ops, lines):
            r = json.loads(ln)
            ops_c[o.op] += 1
            if o.op == "transfer" and o.account == o.to:
                self_transfers += 1
            if r["status"] == "error":
                errs += 1; err_c[r["error"]] += 1
                if o.amount is not None and o.amount == 0: cov["I3 zero amount rejected"] += 1
                if o.amount is not None and o.amount < 0: cov["I3 negative amount rejected"] += 1
                if o.op in ("deposit", "withdraw", "transfer"): cov["I5 rejected transaction (state must not change)"] += 1
                if o.op == "transfer": cov["I5 rejected transfer"] += 1
            else:
                bal = dict(r["accounts"])
                if o.op == "transfer": cov["I2 accepted transfer"] += 1
                if o.op == "withdraw" and bal.get(o.account) == 0: cov["I1 withdrawal to exactly zero"] += 1
                if o.op == "transfer" and bal.get(o.account) == 0: cov["I1 transfer emptying the source"] += 1
                if o.op in ("deposit", "transfer"):
                    tgt = o.account if o.op == "deposit" else o.to
                    if bal.get(tgt) == M: cov["I1 balance reaching exactly M"] += 1
                prev_bal = bal
        inv_share.append(errs / len(ops))
        violations += len(check_run(ops, lines))
    total_ops = sum(lengths)
    total_err = sum(err_c.values())
    return {
        "files": len(files),
        "operations": total_ops,
        "length_min_max": [min(lengths), max(lengths)],
        "accounts_created_min_mean_max": [min(accounts), round(statistics.mean(accounts), 1), max(accounts)],
        "self_transfers": self_transfers,
        "invalid_share_overall": round(total_err / total_ops, 4),
        "invalid_share_per_sequence_min_mean_max": [round(min(inv_share), 3), round(statistics.mean(inv_share), 3), round(max(inv_share), 3)],
        "operations_by_type": dict(ops_c.most_common()),
        "errors_by_code": dict(err_c.most_common()),
        "invariant_coverage": dict(sorted(cov.items())),
        "oracle_invariant_violations": violations,
    }


BOUNDARIES = {
    "amount 0": lambda o, b: o.amount == 0,
    "amount 1": lambda o, b: o.amount == 1,
    "negative amount": lambda o, b: o.amount is not None and o.amount < 0,
    "smallest i64 amount": lambda o, b: o.amount == -(2**63),
    "withdraw balance - 1": lambda o, b: o.op == "withdraw" and o.account in b and o.amount == b[o.account] - 1,
    "withdraw exactly the balance": lambda o, b: o.op == "withdraw" and o.account in b and o.amount == b[o.account],
    "withdraw balance + 1": lambda o, b: o.op == "withdraw" and o.account in b and o.amount == b[o.account] + 1,
    "transfer balance - 1": lambda o, b: o.op == "transfer" and o.account in b and o.amount == b[o.account] - 1,
    "transfer exactly the balance": lambda o, b: o.op == "transfer" and o.account in b and o.amount == b[o.account],
    "transfer balance + 1": lambda o, b: o.op == "transfer" and o.account in b and o.amount == b[o.account] + 1,
    "amount M": lambda o, b: o.amount == M,
    "deposit to exactly M": lambda o, b: o.op == "deposit" and o.account in b and o.amount is not None and b[o.account] + o.amount == M,
    "deposit 1 above M": lambda o, b: o.op == "deposit" and o.account in b and o.amount is not None and b[o.account] + o.amount == M + 1,
    "transfer destination to exactly M": lambda o, b: o.op == "transfer" and o.to in b and o.amount is not None and b[o.to] + o.amount == M,
    "transfer destination 1 above M": lambda o, b: o.op == "transfer" and o.to in b and o.amount is not None and b[o.to] + o.amount == M + 1,
    "empty account id": lambda o, b: o.op == "create" and o.account == "",
    "duplicate account id": lambda o, b: o.op == "create" and o.account in b,
    "account that does not exist": lambda o, b: o.op != "create" and (o.account not in b or (o.op == "transfer" and o.to not in b)),
    "missing account with invalid amount (check order)": lambda o, b: o.op != "create" and o.account not in b and o.amount is not None and o.amount <= 0,
}


def test_cases() -> dict[str, object]:
    found = {k: [] for k in BOUNDARIES}
    expected_ok = True; violations = 0
    names = sorted(glob.glob(os.path.join(DATA, "tests", "*.csv")))
    for f in names:
        ops = read_csv(f)
        lines = run(ops)
        exp = open(f.replace(".csv", ".expected.jsonl")).read().split("\n")[:-1]
        expected_ok &= (exp == lines)
        violations += len(check_run(ops, lines))
        b: dict[str, int] = {}
        for o, ln in zip(ops, lines):
            for k, fn in BOUNDARIES.items():
                if fn(o, b) and os.path.basename(f)[:4] not in found[k]:
                    found[k].append(os.path.basename(f)[:4])
            b = dict(json.loads(ln)["accounts"])
    return {"files": len(names), "operations": sum(len(read_csv(f)) for f in names),
            "expected_outputs_match_oracle": expected_ok, "oracle_invariant_violations": violations,
            "boundaries": {k: v for k, v in found.items()},
            "boundaries_missing": [k for k, v in found.items() if not v]}


def checker_self_test() -> dict[str, list[str]]:
    """Feed the checker deliberately broken transitions; each must be flagged."""
    def L(step: int, op: str, status: str, accounts: list[list[object]], records: int, last: object, error: object = None) -> str:
        return json.dumps({"step": step, "op": op, "status": status, "error": error, "value": None,
                           "accounts": accounts, "records": records, "last": last}, separators=(",", ":"))
    setup = [Op("create", "A", "", None), Op("create", "B", "", None), Op("deposit", "A", "", 100)]
    base = [L(0, "create", "ok", [["A", 0]], 0, None), L(1, "create", "ok", [["A", 0], ["B", 0]], 0, None),
            L(2, "deposit", "ok", [["A", 100], ["B", 0]], 1, ["deposit", "A", "", 100])]
    cases = {
        "negative balance after withdrawal (DS1-like)": (Op("withdraw", "A", "", 150),
            L(3, "withdraw", "ok", [["A", -50], ["B", 0]], 2, ["withdraw", "A", "", 150])),
        "accepted zero deposit (DS2-like)": (Op("deposit", "A", "", 0),
            L(3, "deposit", "ok", [["A", 100], ["B", 0]], 2, ["deposit", "A", "", 0])),
        "transfer without credit (DS3-like)": (Op("transfer", "A", "B", 40),
            L(3, "transfer", "ok", [["A", 60], ["B", 0]], 2, ["transfer", "A", "B", 40])),
        "accepted operation on missing account (DS5-like)": (Op("deposit", "Z", "", 5),
            L(3, "deposit", "ok", [["A", 100], ["B", 0]], 2, ["deposit", "Z", "", 5])),
        "duplicate create accepted (DS7-like)": (Op("create", "A", "", None),
            L(3, "create", "ok", [["A", 0], ["B", 0]], 1, ["deposit", "A", "", 100])),
        "rejected withdrawal still recorded (DS8-like)": (Op("withdraw", "A", "", 500),
            L(3, "withdraw", "error", [["A", 100], ["B", 0]], 2, ["withdraw", "A", "", 500], "INSUFFICIENT_FUNDS")),
        "balance above M (DS9-like)": (Op("deposit", "A", "", M),
            L(3, "deposit", "ok", [["A", M + 100], ["B", 0]], 2, ["deposit", "A", "", M])),
        "deposit applied with wrong amount": (Op("deposit", "A", "", 10),
            L(3, "deposit", "ok", [["A", 90], ["B", 0]], 2, ["deposit", "A", "", 10])),
    }
    out = {}
    for name, (op, bad) in cases.items():
        res = check_run(setup + [op], base + [bad])
        out[name] = res[-1][1] if res and res[-1][0] == 3 else []
    return out


def main() -> None:
    report = {"reproducibility": reproducibility(), "random_sequences": sequences(),
              "frozen_test_cases": test_cases(), "checker_self_test": checker_self_test()}
    with open(os.path.join(DATA, "validation_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
