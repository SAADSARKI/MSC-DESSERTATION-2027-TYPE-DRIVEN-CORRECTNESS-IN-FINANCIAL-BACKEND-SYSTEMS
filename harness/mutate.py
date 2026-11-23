"""Mutant generation (dissertation Section 3.8).

Seven mutation operators are applied, by this one script, at every place where
they fit in the core library of each program (every source file under
rust/*/src except main.rs, and every module of python/bank except runner.py).
The runners are test drivers and are not mutated, except where a defect
scenario is defined at the caller (DS6 in Rust).

Each mutant is one small change. The thirteen defect scenarios DS1 to DS13 are
defined explicitly below as exact text changes, so they can be inspected.
DS1-DS10 are the original catalogue; DS11-DS13 reproduce failure patterns
observed in an industrial Rust payments backend (see SCENARIOS).

Usage:  python3 mutate.py   -> writes ../results/mutants_<program>.json
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _files(base: str, names: list[str]) -> dict[str, str]:
    return {k: f"{base}/{v}" for k, v in zip(["money", "account_id", "errors", "account", "record", "ledger", "service", "runner"], names)}


_RUST_LAYOUT = ["types/money.rs", "types/account_id.rs", "types/errors.rs", "domain/account.rs", "domain/record.rs",
                "repository/ledger.rs", "services/financial_service.rs", "main.rs"]
_PY_LAYOUT = ["types/money.py", "types/account_id.py", "types/errors.py", "domain/account.py", "domain/record.py",
              "repository/ledger.py", "services/financial_service.py", "runner.py"]

PROGRAMS = {
    "rust_typed": {"lang": "rust", **_files("rust/bank_typed/src", _RUST_LAYOUT)},
    "rust_plain": {"lang": "rust", **_files("rust/bank_plain/src", _RUST_LAYOUT)},
    "python": {"lang": "python", **_files("python/bank", _PY_LAYOUT)},
}
# Rust-Plain has no AccountId type.
del PROGRAMS["rust_plain"]["account_id"]
# Files whose code is mutated by the operators (the runner is not mutated).
CORE_KEYS = ["money", "account_id", "errors", "account", "record", "ledger", "service"]
PAIRS = {"rust": [("from", "to"), ("source", "destination")],
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
    if not t or t.startswith(("//", "#[", "#!", "use ", "pub use ", "pub mod ", "mod ", "pub struct", "pub enum", "impl",
                              "from ", "import ", "@", "class ", '"""')):
        return False
    if t.startswith(("fn ", "pub fn ", "pub(crate) fn ", "def ")):
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
                or re.search(r"self\.accounts\.insert\(|self\._accounts\[[^\]]+\]\s*=", txt) \
                or re.search(r"self\.(_)?accounts\.(push|append)\(", txt) \
                or re.search(r"\b(txn|self\.ledger|self\._ledger)\.(save|record|commit|put|append)\(", txt):
            # Python cannot have an empty block, so a deleted statement leaves
            # `pass` (the same meaning as an empty Rust block).
            yield a, b, ([] if lang == "rust" else [lines[a][: len(lines[a]) - len(lines[a].lstrip())] + "pass"])


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


# ---------------------------------------------------- defect scenarios (Table 3.2)
# Human-readable catalogue: (title, invariant(s), origin, description).
SCENARIOS = {
    "DS1": ("Withdrawal without funds check", "I1", "catalogue",
            "The sufficient-funds check in Account.debit is removed."),
    "DS2": ("Zero amount accepted", "I3", "catalogue",
            "The zero-amount check is removed (Rust-Typed: in Amount::new; others: in deposit)."),
    "DS3": ("Incomplete transfer", "I2", "catalogue",
            "The statement that updates the destination balance in transfer is removed."),
    "DS4": ("Transfer without funds check", "I1", "catalogue",
            "The sufficient-funds check in transfer is removed."),
    "DS5": ("Unchecked account lookup", "I4", "catalogue",
            "The Option/None lookup in Ledger.find is replaced by direct map indexing."),
    "DS6": ("Negative amount at the boundary", "I3", "catalogue",
            "A negative amount reaches deposit (Rust: the runner negates it; Python: <= 0 weakened to == 0)."),
    "DS7": ("Duplicate account identifier", "I4", "catalogue",
            "The duplicate-identifier check in create_account is removed."),
    "DS8": ("Ignored failure result", "I1,I5", "catalogue",
            "The result of Account.debit in withdraw is ignored (Rust: `?` dropped; Python: exception swallowed)."),
    "DS9": ("Numeric overflow on deposit", "I1", "catalogue",
            "The upper-limit check in Account.credit is removed (Rust-Typed: checked_add becomes +)."),
    "DS10": ("Account used before initialisation", "I1,I4", "catalogue",
             "An account is constructed without its balance field."),
    "DS11": ("Write outside the unit of work", "I2,I5", "industrial",
             "transfer debits the source and writes it straight to the ledger before the destination limit check "
             "(a first leg persisted before the second leg is validated)."),
    "DS12": ("Commit despite a stored error", "I5", "industrial",
             "deposit stores the result of Account.credit in a variable, stages and commits anyway, "
             "and only then propagates the error."),
    "DS13": ("Transaction used after commit", "I5", "industrial",
             "withdraw commits the unit of work before staging the transaction record."),
}

_RT_DEP_TAIL = '''        txn.save(account);
        txn.record(TransactionRecord {
            kind: "deposit",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        txn.commit();
        Ok(())'''
_RP_DEP_TAIL = _RT_DEP_TAIL.replace("id.clone()", "id.to_string()").replace("counterparty: None", "counterparty: String::new()")
_RT_WD = '''        txn.save(account);
        txn.record(TransactionRecord {
            kind: "withdraw",
            account: id.clone(),
            counterparty: None,
            amount,
        });
        txn.commit();
'''
_RP_WD = _RT_WD.replace("id.clone()", "id.to_string()").replace("counterparty: None", "counterparty: String::new()")


def _commit_first(block: str) -> str:
    """Move the commit before the record staging (DS13)."""
    lines = block.rstrip("\n").split("\n")
    return "\n".join([lines[0], lines[-1]] + lines[1:-1]) + "\n"


# (DS, file key, old text, new text). Each old text must occur exactly once in that file.
DS = {
    "rust_typed": [
        ("DS1", "account", "        if self.balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS2", "money", "        if value == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]\n", ""),
        ("DS3", "service", "        destination.balance = new_to; // [ENF:I2]\n", ""),
        ("DS4", "service", "        if source.balance < amount.value() { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS5", "ledger", "        let account = self.accounts.get(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]\n",
                          "        let account = &self.accounts[id];\n"),
        ("DS6", "runner", "    let amount = Amount::new(amount?)?;\n    let id = existing_id(account)?;\n    service.deposit(",
                          "    let amount = Amount::new(-(amount? as i64))?;\n    let id = existing_id(account)?;\n    service.deposit("),
        ("DS7", "service", "        if self.ledger.contains(&id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]\n", ""),
        ("DS8", "service", "        account.debit(amount)?;", "        account.debit(amount);"),
        ("DS9", "account", "let new_balance = self.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]",
                           "let new_balance = self.balance + amount.value();"),
        ("DS10", "service", "Account { id, balance: 0 }", "Account { id }"),
        ("DS11", "service",
         "        let new_to = destination.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]\n"
         "        source.balance -= amount.value(); // [ENF:I2]\n",
         "        source.balance -= amount.value(); // [ENF:I2]\n"
         "        self.ledger.put(source.clone());\n"
         "        let new_to = destination.balance.checked_add(amount.value()).ok_or(BankError::BalanceLimitExceeded)?; // [ENF:I1]\n"),
        ("DS12", "service", "        account.credit(amount)?;\n" + _RT_DEP_TAIL,
                            "        let credited = account.credit(amount);\n" + _RT_DEP_TAIL.replace("        Ok(())", "        credited?;\n        Ok(())")),
        ("DS13", "service", _RT_WD, _commit_first(_RT_WD)),
    ],
    "rust_plain": [
        ("DS1", "account", "        if self.balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS2", "service", "    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {\n        if amount == 0 { return Err(BankError::InvalidAmount); } // [ENF:I3]\n",
                           "    pub fn deposit(&mut self, id: &str, amount: u64) -> Result<(), BankError> {\n"),
        ("DS3", "service", "        destination.balance += amount; // [ENF:I2]\n", ""),
        ("DS4", "service", "        if source.balance < amount { return Err(BankError::InsufficientFunds); } // [ENF:I1]\n", ""),
        ("DS5", "ledger", "        let account = self.accounts.get(id).ok_or(BankError::AccountNotFound)?; // [ENF:I4]\n",
                          "        let account = &self.accounts[id];\n"),
        ("DS6", "runner", "    let amount = amount?;\n    service.deposit(account, amount)?;",
                          "    let amount = -(amount? as i64);\n    service.deposit(account, amount)?;"),
        ("DS7", "service", "        if self.ledger.contains(id) { return Err(BankError::DuplicateAccount); } // [ENF:I4]\n", ""),
        ("DS8", "service", "        account.debit(amount)?;", "        account.debit(amount);"),
        ("DS9", "account", "        if amount > M - self.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]\n", ""),
        ("DS10", "service", "Account { id: id.to_string(), balance: 0 }", "Account { id: id.to_string() }"),
        ("DS11", "service",
         "        if amount > M - destination.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]\n"
         "        source.balance -= amount; // [ENF:I2]\n",
         "        source.balance -= amount; // [ENF:I2]\n"
         "        self.ledger.put(source.clone());\n"
         "        if amount > M - destination.balance { return Err(BankError::BalanceLimitExceeded); } // [ENF:I1]\n"),
        ("DS12", "service", "        account.credit(amount)?;\n" + _RP_DEP_TAIL,
                            "        let credited = account.credit(amount);\n" + _RP_DEP_TAIL.replace("        Ok(())", "        credited?;\n        Ok(())")),
        ("DS13", "service", _RP_WD, _commit_first(_RP_WD)),
    ],
    "python": [
        ("DS1", "account", "        if self.balance < amount:  # [ENF:I1]\n            raise InsufficientFunds()\n", ""),
        ("DS2", "service", "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount <= 0:  # [ENF:I3]\n            raise InvalidAmount()\n",
                           "    def deposit(self, account_id: AccountId, amount: int) -> None:\n"),
        ("DS3", "service", "        dst.balance += amount  # [ENF:I2]\n", ""),
        ("DS4", "service", "        if src.balance < amount:  # [ENF:I1]\n            raise InsufficientFunds()\n", ""),
        ("DS5", "ledger", "        acct = self._accounts.get(account_id)\n        if acct is None:  # [ENF:I4]\n            raise AccountNotFound()\n",
                          "        acct = self._accounts[account_id]\n"),
        ("DS6", "service", "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount <= 0:  # [ENF:I3]",
                           "    def deposit(self, account_id: AccountId, amount: int) -> None:\n        if amount == 0:  # [ENF:I3]"),
        ("DS7", "service", "        if self._ledger.contains(account_id):  # [ENF:I4]\n            raise DuplicateAccount()\n", ""),
        ("DS8", "service", "        acct.debit(amount)\n", "        try:\n            acct.debit(amount)\n        except BankError:\n            pass\n"),
        ("DS9", "account", "        if self.balance + amount > M:  # [ENF:I1]\n            raise BalanceLimitExceeded()\n", ""),
        ("DS10", "service", "Account(id=account_id, balance=0)", "Account(id=account_id)"),
        ("DS11", "service",
         "        if dst.balance + amount > M:  # [ENF:I1]\n            raise BalanceLimitExceeded()\n"
         "        src.balance -= amount  # [ENF:I2]\n",
         "        src.balance -= amount  # [ENF:I2]\n        self._ledger.put(src)\n"
         "        if dst.balance + amount > M:  # [ENF:I1]\n            raise BalanceLimitExceeded()\n"),
        ("DS12", "service",
         "        acct.credit(amount)\n        txn.save(acct)\n"
         "        txn.record(TransactionRecord(\"deposit\", account_id.value, \"\", amount))\n        txn.commit()\n",
         "        error: BankError | None = None\n        try:\n            acct.credit(amount)\n        except BankError as e:\n"
         "            error = e\n        txn.save(acct)\n"
         "        txn.record(TransactionRecord(\"deposit\", account_id.value, \"\", amount))\n        txn.commit()\n"
         "        if error is not None:\n            raise error\n"),
        ("DS13", "service",
         "        txn.record(TransactionRecord(\"withdraw\", account_id.value, \"\", amount))\n        txn.commit()\n",
         "        txn.commit()\n        txn.record(TransactionRecord(\"withdraw\", account_id.value, \"\", amount))\n"),
    ],
}
BANK_ERROR_IMPORT = "from bank.types.errors import BankError\n"


def add_missing_import(lang: str, src: str) -> str:
    """A Python mutant that names BankError gets the import it needs, so that it
    fails (or not) because of the defect and not because of a missing name."""
    if lang != "python" or "BankError" not in src or "import BankError" in src or re.search(r"\bBankError,", src):
        return src
    future = "from __future__ import annotations\n"
    if future in src:
        return src.replace(future, future + BANK_ERROR_IMPORT, 1)
    return src.replace('"""\n', '"""\n' + BANK_ERROR_IMPORT, 1)


def generate(program: str) -> list[Mutant]:
    cfg = PROGRAMS[program]
    lang = cfg["lang"]
    muts: list[Mutant] = []
    seen: set[str] = set()
    counters: dict[str, int] = {}
    for key in CORE_KEYS:
        if key not in cfg:
            continue
        rel = cfg[key]
        src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        lines = src.split("\n")
        for name, fn in OPERATORS.items():
            for a, b, repl in fn(lines, lang):
                new_lines = lines[:a] + repl + lines[b + 1:]
                new_src = add_missing_import(lang, "\n".join(new_lines))
                if new_src == src or (rel, new_src) in seen:
                    continue
                seen.add((rel, new_src))
                counters[name] = counters.get(name, 0) + 1
                muts.append(Mutant(f"{program}-{name}-{counters[name]:02d}", program, "operator", name, rel, a + 1,
                                   "\n".join(lines[a:b + 1]).strip(), "\n".join(repl).strip(), new_src))
    for ds, key, old, new in DS[program]:
        rel = cfg[key]
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert text.count(old) == 1, (program, ds, text.count(old))
        line = text[: text.index(old)].count("\n") + 1
        mutated = add_missing_import(lang, text.replace(old, new))
        muts.append(Mutant(f"{program}-{ds}", program, "scenario", ds, rel, line, old.strip(), new.strip(), mutated))
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
