"""Independent invariant checker (SPEC.md Section 1, dissertation Section 3.6.2).

It does not recompute the expected result of an operation. It looks only at
the operation, the state before it and the state after it, as printed by a
program, and reports every invariant that the transition breaks. It therefore
works on the output of any program, correct or defective.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from model import Op

M = 2**64 - 1
TX_OPS = ("deposit", "withdraw", "transfer")


def state(line: Optional[dict[str, Any]]) -> tuple[dict[str, int], int, Any]:
    if line is None:
        return {}, 0, None
    return {k: v for k, v in line["accounts"]}, line["records"], line["last"]


def check_step(o: Op, before: Optional[dict[str, Any]], after: dict[str, Any]) -> list[str]:
    """Return a list of violation labels such as 'I1', 'I2'."""
    v: list[str] = []
    a0, r0, _ = state(before)
    a1, r1, last1 = state(after)
    ok = after["status"] == "ok"

    # I1: balance limits
    if any((not isinstance(b, int)) or b < 0 or b > M for b in a1.values()):
        v.append("I1")

    # I3: every accepted transaction has a positive amount
    if ok and o.op in TX_OPS and (o.amount is None or o.amount <= 0):
        v.append("I3")

    # I4: account identity
    ids0, ids1 = set(a0), set(a1)
    if not ids0 <= ids1:
        v.append("I4")  # an account disappeared or was renamed
    if o.op == "create":
        if ok and (o.account == "" or o.account in ids0 or ids1 != ids0 | {o.account}):
            v.append("I4")
    else:
        if ids1 != ids0:
            v.append("I4")  # only create may add an account
        named = [o.account] + ([o.to] if o.op == "transfer" else [])
        if ok and any(n not in ids0 for n in named):
            v.append("I4")  # accepted an operation on a missing account

    # I5: atomicity. A rejected operation changes nothing.
    if not ok:
        if a1 != a0 or r1 != r0:
            v.append("I5")
    else:
        touched = {o.account} | ({o.to} if o.op == "transfer" else set())
        if o.op == "create":
            touched = {o.account}
        changed = {k for k in ids0 if a0[k] != a1.get(k)}
        if not changed <= touched:
            v.append("I5")  # an untouched account changed
        expect_r = r0 + (1 if o.op in TX_OPS else 0)
        if r1 != expect_r:
            v.append("I5")
        if o.op in TX_OPS and o.amount is not None:
            exp_last = [o.op, o.account, o.to if o.op == "transfer" else "", o.amount]
            if last1 != exp_last:
                v.append("I5")
        if o.op == "transfer" and o.amount is not None and o.account in a0 and o.to in a0:
            if a1.get(o.account) != a0[o.account] - o.amount or a1.get(o.to) != a0[o.to] + o.amount:
                v.append("I5")  # one side not applied, or applied with a different amount

    # I2: conservation of value for an accepted transfer
    if ok and o.op == "transfer":
        if sum(a1.values()) != sum(a0.values()):
            v.append("I2")
    # An accepted deposit or withdrawal must change the account by exactly the
    # amount requested; otherwise the operation was not applied as requested (I5).
    if ok and o.op in ("deposit", "withdraw") and o.amount is not None and o.account in a0:
        delta = o.amount if o.op == "deposit" else -o.amount
        if a1.get(o.account) != a0[o.account] + delta:
            v.append("I5")

    return sorted(set(v))


def check_run(ops: list[Op], lines: list[str]) -> list[tuple[int, list[str]]]:
    """Check a whole run. Returns [(step, violations)] for steps with violations."""
    bad = []
    prev: Optional[dict[str, Any]] = None
    for i, (o, ln) in enumerate(zip(ops, lines)):
        cur = json.loads(ln)
        viol = check_step(o, prev, cur)
        if viol:
            bad.append((i, viol))
        prev = cur
    return bad
