"""Data generator (dissertation Section 3.8.1).

Produces, from one fixed seed:
  data/tests/      frozen test cases: CSV input + expected JSON-lines output
  data/sequences/  1,000 random sequences of 50 operations, 5 to 20 accounts,
                   about 30 per cent invalid operations
  data/manifest.json  seed, counts and SHA-256 hash of every file

Usage:  python3 generate.py [--seed 2026] [--out ../data]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random

from model import M, Op, run, write_csv

SEED = 2026
N_SEQ = 1000
SEQ_LEN = 50
MIN_ACC, MAX_ACC = 5, 20
P_INVALID = 0.30
I64_MIN = -(2**63)


# ---------------------------------------------------------------- test cases
def C(a: str) -> Op: return Op("create", a, "", None)
def B(a: str) -> Op: return Op("balance", a, "", None)
def D(a: str, x: int) -> Op: return Op("deposit", a, "", x)
def W(a: str, x: int) -> Op: return Op("withdraw", a, "", x)
def T(a: str, b: str, x: int) -> Op: return Op("transfer", a, b, x)


def test_cases() -> dict[str, list[Op]]:
    return {
        "tc01_create_and_identity": [
            C("A001"), C("A001"), C(""), C("A002"), B("A001"), B("X999"), B("A002"),
        ],
        "tc02_deposit_amounts": [
            C("A001"), D("A001", 0), D("A001", -1), D("A001", I64_MIN), D("A001", 1),
            D("A001", 5000), D("X999", 100), D("X999", -5), D("X999", 0), B("A001"),
        ],
        "tc03_deposit_limit": [
            C("A001"), D("A001", M), D("A001", 1), B("A001"),
            C("A002"), D("A002", M - 10), D("A002", 11), D("A002", 10), D("A002", 1), B("A002"),
        ],
        "tc04_withdraw_boundaries": [
            C("A001"), C("A002"), C("A003"), D("A001", 1000), D("A002", 1000), D("A003", 1000),
            W("A001", 0), W("A001", -1), W("A001", I64_MIN),
            W("A001", 999), W("A002", 1000), W("A003", 1001),
            W("A001", 1), W("A001", 1), W("X999", 5), W("X999", -5),
            B("A001"), B("A002"), B("A003"),
        ],
        "tc05_transfer_boundaries": [
            C("A001"), C("A002"), C("A003"), D("A001", 1000), D("A003", 1000),
            T("A001", "A002", 0), T("A001", "A002", -1), T("A001", "A002", I64_MIN),
            T("A001", "A002", 1001), T("A001", "A002", 1000), T("A002", "A001", 999),
            T("A003", "A002", 1), T("X999", "A001", 5), T("A001", "X999", 5),
            T("X998", "X999", 5), T("X998", "X999", 0),
            B("A001"), B("A002"), B("A003"),
        ],
        "tc06_transfer_limit": [
            C("A001"), C("A002"), C("A003"), D("A001", 100), D("A002", M - 5),
            T("A001", "A002", 6), T("A001", "A002", 5), T("A001", "A002", 1),
            T("A003", "A002", 10), T("A002", "A001", M),
            B("A001"), B("A002"), B("A003"),
        ],
        "tc07_atomicity": [
            C("A001"), C("A002"), D("A001", 700), D("A002", 300),
            T("A001", "A002", 701), W("A002", 301), D("A001", 0), C("A001"),
            T("A001", "A002", 700), W("A002", 1000), B("A001"), B("A002"),
            T("A002", "A001", 1000), D("A001", M), B("A001"),
        ],
        "tc08_conservation_many_accounts": (
            [C(f"A{i:03d}") for i in range(1, 21)]
            + [D(f"A{i:03d}", 10_000 * i) for i in range(1, 21)]
            + [T(f"A{i:03d}", f"A{i % 20 + 1:03d}", 7_000 * i) for i in range(1, 21)]
            + [B(f"A{i:03d}") for i in range(1, 21)]
        ),
        "tc09_large_values": [
            C("A001"), C("A002"), D("A001", M), W("A001", M), D("A001", M - 1),
            T("A001", "A002", M - 1), W("A002", M), W("A002", M - 1), B("A001"), B("A002"),
        ],
        "tc10_missing_accounts_order": [
            C("A001"), D("A001", 50), B("X999"), D("X999", 1), W("X999", 1),
            T("A001", "X999", 51), T("X999", "A001", 1), T("A001", "X999", -3),
            C("X999"), B("X999"), T("A001", "X999", 50), B("X999"), B("A001"),
        ],
    }


# ---------------------------------------------------------- random sequences
def amount(rng: random.Random) -> int:
    r = rng.random()
    if r < 0.05:
        return rng.randint(M // 2, M)          # very large, makes the limit reachable
    if r < 0.15:
        return rng.randint(1, 100)
    return rng.randint(100, 10_000_000)


def sequence(rng: random.Random) -> list[Op]:
    n_acc = rng.randint(MIN_ACC, MAX_ACC)
    ids = [f"A{i:02d}" for i in range(1, n_acc + 1)]
    bal: dict[str, int] = {}
    ops: list[Op] = []
    while len(ops) < SEQ_LEN:
        existing = sorted(bal)
        missing = [i for i in ids if i not in bal]
        # The first operation always creates an account so that later ones have a target.
        if not existing:
            a = missing[0]; ops.append(C(a)); bal[a] = 0; continue
        if rng.random() < P_INVALID:
            o = invalid_op(rng, bal, existing)
        else:
            o = valid_op(rng, bal, existing, missing)
        if o is not None:
            ops.append(o)
    return ops


def valid_op(rng: random.Random, bal: dict[str, int], existing: list[str], missing: list[str]) -> Op | None:
    kinds = ["deposit", "withdraw", "transfer", "balance"] + (["create"] * 3 if missing else [])
    k = rng.choice(kinds)
    if k == "create":
        a = missing[0]; bal[a] = 0; return C(a)
    a = rng.choice(existing)
    if k == "balance":
        return B(a)
    if k == "deposit":
        room = M - bal[a]
        if room == 0:
            return None
        x = min(amount(rng), room)
        if rng.random() < 0.05:
            x = room                              # deposit exactly to the limit
        bal[a] += x; return D(a, x)
    if k == "withdraw":
        if bal[a] == 0:
            return None
        x = bal[a] if rng.random() < 0.15 else rng.randint(1, bal[a])
        bal[a] -= x; return W(a, x)
    # transfer between two different existing accounts (assumption A6)
    if len(existing) < 2 or bal[a] == 0:
        return None
    b = rng.choice([e for e in existing if e != a])
    room = M - bal[b]
    if room == 0:
        return None
    x = min(rng.randint(1, bal[a]), room)
    if rng.random() < 0.15:
        x = min(bal[a], room)
    bal[a] -= x; bal[b] += x
    return T(a, b, x)


def invalid_op(rng: random.Random, bal: dict[str, int], existing: list[str]) -> Op | None:
    kind = rng.choice(["zero", "negative", "missing", "duplicate", "empty_id",
                       "insufficient", "insufficient", "limit"])
    a = rng.choice(existing)
    op = rng.choice(["deposit", "withdraw", "transfer"])
    others = [e for e in existing if e != a]
    def mk(x: int, src: str = a, dst: str | None = None) -> Op | None:
        if op == "transfer":
            if dst is None:
                if not others:
                    return None
                dst = rng.choice(others)
            return T(src, dst, x)
        return D(src, x) if op == "deposit" else W(src, x)
    if kind == "zero":
        return mk(0)
    if kind == "negative":
        return mk(-rng.choice([1, rng.randint(2, 10_000_000), 2**63]))
    if kind == "missing":
        ghost = "X" + str(rng.randint(10, 99))
        which = rng.random()
        if op == "transfer" and which < 0.5:
            return mk(rng.randint(1, 1000), a, ghost)   # missing destination
        if rng.random() < 0.3:
            return B(ghost)
        return mk(rng.randint(1, 1000), ghost, a if op == "transfer" else None)
    if kind == "duplicate":
        return C(a)
    if kind == "empty_id":
        return C("")
    if kind == "insufficient":
        if op == "deposit":
            op = "withdraw"
        return mk(bal[a] + rng.randint(1, 1000)) if bal[a] < M else None
    # limit: deposit (or transfer) that would push a balance above M
    room = M - bal[a]
    if op == "transfer" and others:
        src = rng.choice(others)
        if bal[src] > room:                      # funds suffice, destination would overflow
            return T(src, a, rng.randint(room + 1, bal[src]))
    return D(a, room + rng.randint(1, min(1000, M - room) if room < M else 1)) if room < M else D(a, 1)


# ------------------------------------------------------------------- driver
def sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    tdir, sdir = os.path.join(out, "tests"), os.path.join(out, "sequences")
    os.makedirs(tdir, exist_ok=True); os.makedirs(sdir, exist_ok=True)
    files: dict[str, str] = {}

    for name, ops in test_cases().items():
        p = os.path.join(tdir, name + ".csv"); write_csv(p, ops)
        e = os.path.join(tdir, name + ".expected.jsonl")
        with open(e, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(run(ops)) + "\n")
        files[os.path.relpath(p, out)] = sha(p); files[os.path.relpath(e, out)] = sha(e)

    master = random.Random(args.seed)
    for i in range(N_SEQ):
        rng = random.Random(master.getrandbits(64))
        ops = sequence(rng)
        p = os.path.join(sdir, f"seq_{i:04d}.csv"); write_csv(p, ops)
        files[os.path.relpath(p, out)] = sha(p)

    manifest = {"seed": args.seed, "sequences": N_SEQ, "sequence_length": SEQ_LEN,
                "accounts_per_sequence": [MIN_ACC, MAX_ACC], "target_invalid_share": P_INVALID,
                "M": str(M), "files": dict(sorted(files.items()))}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    print(f"wrote {len(files)} files to {out} (seed {args.seed})")


if __name__ == "__main__":
    main()
