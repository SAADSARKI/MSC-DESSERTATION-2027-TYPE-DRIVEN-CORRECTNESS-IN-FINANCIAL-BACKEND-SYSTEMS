"""Reference model (test oracle).

An independent, deliberately simple implementation of the rules in SPEC.md
Section 1. It is used only to produce the expected outputs of the frozen test
cases and to classify generated operations as valid or invalid. It is not one
of the programs under test and is never mutated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

M = 2**64 - 1


@dataclass
class Op:
    op: str
    account: str
    to: str
    amount: Optional[int]

    def csv(self) -> str:
        a = "" if self.amount is None else str(self.amount)
        return f"{self.op},{self.account},{self.to},{a}"


@dataclass
class Model:
    accounts: dict[str, int] = field(default_factory=dict)
    records: list[tuple[str, str, str, int]] = field(default_factory=list)

    def apply(self, o: Op) -> tuple[Optional[str], Optional[int]]:
        """Return (error_code or None, value or None); mutate state only on success."""
        if o.op == "create":
            if o.account == "":
                return "INVALID_ACCOUNT_ID", None
            if o.account in self.accounts:
                return "DUPLICATE_ACCOUNT", None
            self.accounts[o.account] = 0
            return None, None
        if o.op == "balance":
            if o.account not in self.accounts:
                return "ACCOUNT_NOT_FOUND", None
            return None, self.accounts[o.account]
        x = o.amount
        assert x is not None
        if x <= 0:
            return "INVALID_AMOUNT", None
        if o.op == "deposit":
            if o.account not in self.accounts:
                return "ACCOUNT_NOT_FOUND", None
            if self.accounts[o.account] + x > M:
                return "BALANCE_LIMIT_EXCEEDED", None
            self.accounts[o.account] += x
            self.records.append(("deposit", o.account, "", x))
            return None, None
        if o.op == "withdraw":
            if o.account not in self.accounts:
                return "ACCOUNT_NOT_FOUND", None
            if self.accounts[o.account] < x:
                return "INSUFFICIENT_FUNDS", None
            self.accounts[o.account] -= x
            self.records.append(("withdraw", o.account, "", x))
            return None, None
        if o.op == "transfer":
            if o.account not in self.accounts or o.to not in self.accounts:
                return "ACCOUNT_NOT_FOUND", None
            if self.accounts[o.account] < x:
                return "INSUFFICIENT_FUNDS", None
            if self.accounts[o.to] + x > M:
                return "BALANCE_LIMIT_EXCEEDED", None
            self.accounts[o.account] -= x
            self.accounts[o.to] += x
            self.records.append(("transfer", o.account, o.to, x))
            return None, None
        raise ValueError(o.op)

    def line(self, step: int, o: Op, err: Optional[str], value: Optional[int]) -> str:
        last = list(self.records[-1]) if self.records else None
        obj = {
            "step": step,
            "op": o.op,
            "status": "error" if err else "ok",
            "error": err,
            "value": value,
            "accounts": [[k, self.accounts[k]] for k in sorted(self.accounts)],
            "records": len(self.records),
            "last": last,
        }
        return json.dumps(obj, separators=(",", ":"))


def run(ops: list[Op]) -> list[str]:
    m = Model()
    out = []
    for i, o in enumerate(ops):
        err, val = m.apply(o)
        out.append(m.line(i, o, err, val))
    return out


def read_csv(path: str) -> list[Op]:
    ops = []
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip()
        assert header == "op,account,to,amount", header
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln:
                continue
            op, acc, to, amt = ln.split(",")
            ops.append(Op(op, acc, to, int(amt) if amt != "" else None))
    return ops


def write_csv(path: str, ops: list[Op]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("op,account,to,amount\n")
        for o in ops:
            f.write(o.csv() + "\n")
