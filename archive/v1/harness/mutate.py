"""Mutant generation (dissertation Section 3.7.1).

Seven mutation operators are applied, by this one script, at every place where
they fit in the core library of each program (rust/*/src/lib.rs and
python/bank/core.py). The runners are test drivers and are not mutated, except
where a defect scenario in Table 3 is defined at the caller (DS6 in Rust).

Each mutant is one small change. The ten defect scenarios DS1 to DS10 are
defined explicitly below as exact text changes, so they can be inspected.

Usage:  python3 mutate.py   -> writes ../results/mutants_<program>.json
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PROGRAMS = {
    "rust_typed": {"lang": "rust", "core": "rust/bank_typed/src/lib.rs", "runner": "rust/bank_typed/src/main.rs"},
    "rust_plain": {"lang": "rust", "core": "rust/bank_plain/src/lib.rs", "runner": "rust/bank_plain/src/main.rs"},
    "python": {"lang": "python", "core": "python/bank/core.py", "runner": "python/bank/runner.py"},
}
PAIRS = {"rust": [("from", "to"), ("from_balance", "to_balance"), ("source", "destination")],
         "python": [("from_id", "to_id"), ("src", "dst")]}


@dataclass
class Mutant:
    id: str
    program: str
    kind: str          # "operator" or "scenario"
    operator: str      # operator name or DS number
    file: str          # relative path of the changed file
    line: int          # 1-based line of the change
    before: str
    after: str
    source: str        # whole changed file


# ------------------------------------------------------------ statement split
def statements(lines: list[str]) -> list[tuple[int, int]]:
    """Group lines into statements: a statement continues while ( or [ are open."""
    out, i = [], 0
    while i < len(lines):
        depth, j = 0, i
        while True:
            code = re.sub(r'"[^"]*"', '""', lines[j].split("//")[0].split("  #")[0])
            depth += sum(code.count(c) for c in "([") - sum(code.count(c) for c in ")]")
            if depth <= 0 or j == len(lines) - 1:
                break
            j += 1
        out.append((i, j)); i = j + 1
    return out


def is_code(s: str, lang: str) -> bool:
    t = s.strip()
    if not t or t.startswith(("//", "#[", "#!", "use ", "pub struct", "pub enum", "impl", "from ", "import ", "@", "class ", '"""')):
        return False
    if t.startswith(("fn ", "pub fn ", "def ")):
        return False
    return True


# ------------------------------------------------------------------ operators
CMP = {"<=": "<", ">=": ">", "==": "!=", "!=": "==", "<": "<=", ">": ">="}


def op_remove_check(lines: list[str], lang: str):
    for i, s in enumerate(lines):
        t = s.strip()
        if lang == "rust":
            if re.match(r"if .*\{ return Err\(.*\); \}", t):
                yield i, i, []                                   # delete the check line
            m = re.search(r"(\S+)\.checked_add\((.+?)\)\.ok_or\([^)]*\)\?", s)
            if m:
                yield i, i, [s[:m.start()] + f"{m.group(1)} + {m.group(2)}" + s[m.end():]]
        else:
            if t.startswith("if ") and t.split("#")[0].rstrip().endswith(":") and i + 1 < len(lines) \
                    and lines[i + 1].strip().startswith("raise "):
                ind = s[: len(s) - len(s.lstrip())]
                yield i, i + 1, [ind + "pass"]


def op_change_comparison(lines: list[str], lang: str):
    for i, s in enumerate(lines):
        t = s.strip()
        if not t.startswith("if ") or not is_code(s, lang):
            continue
        code = s.split("//")[0] if lang == "rust" else s.split("#")[0]
        for m in re.finditer(r"<=|>=|==|!=|(?<![-=])>|<", code):
            yield i, i, [s[:m.start()] + CMP[m.group(0)] + s[m.end():]]


def op_change_arithmetic(lines: list[str], lang: str):
    for i, s in enumerate(lines):
        if not is_code(s, lang):
            continue
        code = s.split("//")[0] if lang == "rust" else s.split("  #")[0]
        for m in re.finditer(r"\+=|-=| \+ | - |checked_add", code):
            rep = {"+=": "-=", "-=": "+=", " + ": " - ", " - ": " + ", "checked_add": "checked_sub"}[m.group(0)]
            yield i, i, [s[:m.start()] + rep + s[m.end():]]


def op_delete_statement(lines: list[str], lang: str):
    for a, b in statements(lines):
        txt = " ".join(lines[a:b + 1])
        if not is_code(lines[a], lang):
            continue
        if re.search(r"\.balance\s*(\+=|-=|=(?!=))", txt) or re.search(r"\.(records\.push|_records\.append)\(", txt) \
                or re.search(r"self\.accounts\.insert\(|self\._accounts\[[^\]]+\]\s*=", txt):
            yield a, b, []


def op_ignore_error(lines: list[str], lang: str):
    for i, s in enumerate(lines):
        t = s.split("//")[0].strip() if lang == "rust" else s.split("#")[0].strip()
        if lang == "rust" and re.match(r"^[\w\.]+\.(debit|credit)\(.*\)\?;$", t):
            yield i, i, [s.replace(")?;", ");", 1)]
        if lang == "python" and re.match(r"^[\w\.]+\.(debit|credit)\(.*\)$", t):
            ind = s[: len(s) - len(s.lstrip())]
            yield i, i, [ind + "try:", ind + "    " + s.strip(), ind + "except BankError:", ind + "    pass"]


def op_direct_access(lines: list[str], lang: str):
    for i, s in enumerate(lines):
        if lang == "rust":
            m = re.search(r"\.(get|get_mut)\(([^)]*)\)\.ok_or\(BankError::AccountNotFound\)\?", s)
            if m:
                yield i, i, [s[:m.start()] + f".{m.group(1)}({m.group(2)}).unwrap()" + s[m.end():]]
        else:
            m = re.search(r"self\._accounts\.get\(([^)]*)\)", s)
            if m:
                yield i, i, [s[:m.start()] + f"self._accounts[{m.group(1)}]" + s[m.end():]]


def op_swap_arguments(lines: list[str], lang: str):
    for a, b in statements(lines):
        if not is_code(lines[a], lang):
            continue
        block = "\n".join(lines[a:b + 1])
        for x, y in PAIRS[lang]:
            def use_positions(tok: str) -> list[re.Match[str]]:
                res = []
                for m in re.finditer(rf"\b{tok}\b", block):
                    before, after = block[:m.start()], block[m.end():]
                    if re.search(r"\blet\s+(mut\s+)?$", before):
                        continue                         # declaration target
                    if re.match(r"\s*=(?!=)", after) or re.match(r"\s*:", after) and lang == "python":
                        continue                         # assignment target
                    if lang == "rust" and re.match(r"\s*:\s*&", after):
                        continue                         # parameter declaration
                    res.append(m)
                return res
            ms = sorted(use_positions(x) + use_positions(y), key=lambda m: m.start())
            if not ms:
                continue
            new, last = "", 0
            for m in ms:
                new += block[last:m.start()] + (y if m.group(0) == x else x); last = m.end()
            new += block[last:]
            yield a, b, new.split("\n")


OPERATORS = {
    "remove_check": op_remove_check,
    "change_comparison": op_change_comparison,
    "change_arithmetic": op_change_arithmetic,
    "delete_statement": op_delete_statement,
    "ignore_error": op_ignore_error,
    "direct_access": op_direct_access,
    "swap_arguments": op_swap_arguments,
}


# ---------------------------------------------------- defect scenarios (Table 3)
# (DS, file key, old text, new text). Each old text must occur exactly once.
DS = {
    "rust_typed": [
        ("DS1", "core", "        if self.balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS2", "core", "        if value == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]\n", ""),
        ("DS3", "core", "        destination.balance = new_to; // [ENF:I2]\n", ""),
        ("DS4", "core", "        if from_balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS5", "core", "        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]\n        account.debit(amount)?;",
                        "        let account = self.accounts.get_mut(id).unwrap();\n        account.debit(amount)?;"),
        ("DS6", "runner", "    let amount = Amount::new(amount?)?;\n    let id = existing_id(account)?;\n    service.deposit(",
                          "    let amount = Amount::new(-(amount? as i64))?;\n    let id = existing_id(account)?;\n    service.deposit("),
        ("DS7", "core", "        if self.accounts.contains_key(&id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]\n", ""),
        ("DS8", "core", "        account.debit(amount)?;", "        account.debit(amount);"),
        ("DS9", "core", "let new_balance = self.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]",
                        "let new_balance = self.balance + amount.value();"),
        ("DS10", "core", "Account { id: id.clone(), balance: 0 }", "Account { id: id.clone() }"),
    ],
    "rust_plain": [
        ("DS1", "core", "        if self.balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS2", "core", "    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {\n        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]\n",
                        "    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {\n"),
        ("DS3", "core", "        destination.balance += amount; // [ENF:I2]\n", ""),
        ("DS4", "core", "        if from_balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS5", "core", "        let account = self.accounts.get_mut(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]\n        account.debit(amount)?;",
                        "        let account = self.accounts.get_mut(id).unwrap();\n        account.debit(amount)?;"),
        ("DS6", "runner", "    let amount = amount?;\n    service.deposit(account, amount)?;",
                          "    let amount = -(amount? as i64);\n    service.deposit(account, amount)?;"),
        ("DS7", "core", "        if self.accounts.contains_key(id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]\n", ""),
        ("DS8", "core", "        account.debit(amount)?;", "        account.debit(amount);"),
        ("DS9", "core", "        if amount > M - self.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]\n", ""),
        ("DS10", "core", "Account { id: id.to_string(), balance: 0 }", "Account { id: id.to_string() }"),
    ],
    "python": [
        ("DS1", "core", "        if self.balance < amount:  # [ENF:I1]\n            raise InsufficientFunds()\n", ""),
        ("DS2", "core", "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount <= 0:  # [ENF:I3]\n            raise InvalidAmount()\n",
                        "    def deposit(self, account_id: AccountId, amount: int) -> None:\n"),
        ("DS3", "core", "        dst.balance += amount  # [ENF:I2]\n", ""),
        ("DS4", "core", "        if src.balance < amount:  # [ENF:I1]\n            raise InsufficientFunds()\n", ""),
        ("DS5", "core", "        acct = self._accounts.get(account_id)\n        if acct is None:  # [ENF:I4]\n            raise AccountNotFound()\n        acct.debit(amount)",
                        "        acct = self._accounts[account_id]\n        if acct is None:  # [ENF:I4]\n            raise AccountNotFound()\n        acct.debit(amount)"),
        ("DS6", "core", "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount <= 0:  # [ENF:I3]",
                        "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount == 0:  # [ENF:I3]"),
        ("DS7", "core", "        if account_id in self._accounts:  # [ENF:I4]\n            raise DuplicateAccount()\n", ""),
        ("DS8", "core", "        acct.debit(amount)\n", "        try:\n            acct.debit(amount)\n        except BankError:\n            pass\n"),
        ("DS9", "core", "        if self.balance + amount > M:  # [ENF:I1]\n            raise BalanceLimitExceeded()\n", ""),
        ("DS10", "core", "Account(id=account_id, balance=0)", "Account(id=account_id)"),
    ],
}


def generate(program: str) -> list[Mutant]:
    cfg = PROGRAMS[program]
    lang = cfg["lang"]
    src = open(os.path.join(ROOT, cfg["core"]), encoding="utf-8").read()
    lines = src.split("\n")
    muts: list[Mutant] = []
    seen: set[str] = set()
    for name, fn in OPERATORS.items():
        n = 0
        for a, b, repl in fn(lines, lang):
            new_lines = lines[:a] + repl + lines[b + 1:]
            new_src = "\n".join(new_lines)
            if new_src == src or new_src in seen:
                continue
            seen.add(new_src); n += 1
            muts.append(Mutant(f"{program}-{name}-{n:02d}", program, "operator", name, cfg["core"], a + 1,
                               "\n".join(lines[a:b + 1]).strip(), "\n".join(repl).strip(), new_src))
    for ds, key, old, new in DS[program]:
        rel = cfg[key]
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert text.count(old) == 1, (program, ds, text.count(old))
        line = text[: text.index(old)].count("\n") + 1
        muts.append(Mutant(f"{program}-{ds}", program, "scenario", ds, rel, line, old.strip(), new.strip(),
                           text.replace(old, new)))
    return muts


def main() -> None:
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    for p in PROGRAMS:
        ms = generate(p)
        with open(os.path.join(ROOT, "results", f"mutants_{p}.json"), "w") as f:
            json.dump([{k: v for k, v in asdict(m).items() if k != "source"} for m in ms], f, indent=1)
        from collections import Counter
        c = Counter(m.operator for m in ms if m.kind == "operator")
        print(p, sum(c.values()), "operator mutants", dict(c), "+", sum(m.kind == "scenario" for m in ms), "scenarios")


if __name__ == "__main__":
    main()
