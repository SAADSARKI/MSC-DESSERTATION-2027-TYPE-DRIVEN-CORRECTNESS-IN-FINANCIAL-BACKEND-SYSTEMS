# Build Specification: Financial Backend in Rust and Python

**Version 2 (2026-11-23).** Version 1 is preserved in `archive/v1/`. Version 2 keeps every externally visible behaviour of version 1 (Sections 1 and 4: operations, error codes, order of checks, CSV input, JSON output), so the frozen tests, random sequences, oracle and checker are unchanged. It changes only the internal structure (Section 2), which now follows the layering of an industrial Rust payments backend: value types, domain entities, a repository with a unit of work (transaction), and services. It also adds three defect scenarios (DS11–DS13) drawn from failure patterns observed in that backend.

**Project:** MSc dissertation, "Type-Driven Correctness in Financial Backend Systems: An Empirical Evaluation of Compile-Time Verification Using Rust" (Sa'ad Abdullahi Sarki, Crescent University Abeokuta).

**What you are building:** three small programs that implement the *same* in-memory banking backend:

| Program | Language | Folder |
|---|---|---|
| Rust-Typed | Rust, type-driven design (rules R1 to R5) | `rust/bank_typed` |
| Rust-Plain | Rust, plain values and explicit checks | `rust/bank_plain` |
| Python | Python with runtime validation and full type hints | `python/bank` |

The Python program is used in two configurations later (with and without mypy), but it is **one** program.

These programs are the *correct* baseline of a controlled experiment. Later, small defects will be inserted into copies of them one at a time, and an external test harness will record whether each defect is caught at compile time, by mypy, by testing, or not at all. Because of that, the programs must follow this specification **exactly**: same operations, same order of checks, same error codes, same output format, and no extra features. Do not add anything that is not asked for. Code that is never exercised by the tests distorts the experiment.

The test harness, test data and defect pipeline are **not** part of this task.

---

## 1. Domain rules

Money is in one currency and is stored as **whole kobo** (integers). There are no fees, interest, overdrafts, currencies, users, login, persistence, networking or concurrency. All state is in memory. Operations run one at a time.

Let `M = 2^64 − 1 = 18446744073709551615` (the largest value of a `u64`).

### Operations

| Operation | Input | Accepted when | Effect when accepted |
|---|---|---|---|
| `create` | account id | id is valid (non-empty) and not already in use | new account with balance 0 |
| `balance` | account id | account exists | returns the balance; no state change, no record |
| `deposit` | account id, amount x | x > 0, account exists, balance + x ≤ M | balance += x; one record |
| `withdraw` | account id, amount x | x > 0, account exists, balance ≥ x | balance −= x; one record |
| `transfer` | from id, to id, amount x | x > 0, both accounts exist, balance(from) ≥ x, balance(to) + x ≤ M | balance(from) −= x and balance(to) += x together; one record |

The test tools never transfer money from an account to itself (study assumption A6). **Do not add a same-account check.** Implement the transfer so that it compiles and runs, and do not rely on `from != to` anywhere.

### The five invariants

These are what the programs protect. Use their labels in the enforcement tags (Section 5).

* **I1, balance limits:** every balance stays in `0 ≤ balance ≤ M`.
* **I2, conservation of value:** a transfer does not change the total of all balances.
* **I3, valid amount:** the amount of every accepted deposit, withdrawal and transfer is greater than 0.
* **I4, account identity:** an id is created only once and never changed; an operation on an account that does not exist is rejected.
* **I5, atomicity:** an operation is either fully applied or not applied at all. A rejected operation changes nothing, not even the record list. A transfer never applies only one side.

### Error codes (identical in all three programs)

| Code | When |
|---|---|
| `INVALID_ACCOUNT_ID` | `create` with an empty id |
| `DUPLICATE_ACCOUNT` | `create` with an id already in use |
| `ACCOUNT_NOT_FOUND` | any other operation naming an account that does not exist |
| `INVALID_AMOUNT` | amount ≤ 0 |
| `INSUFFICIENT_FUNDS` | withdrawal or transfer larger than the source balance |
| `BALANCE_LIMIT_EXCEEDED` | deposit or transfer that would take a balance above M |

### Order of checks (mandatory, so that every program returns the same code)

* `create`: id valid → id not in use.
* `balance`: account exists.
* `deposit`: amount valid → account exists → limit.
* `withdraw`: amount valid → account exists → sufficient funds.
* `transfer`: amount valid → source exists → destination exists → sufficient funds in source → destination limit.

All checks happen **before** any state is changed.

### Transaction records

Every accepted deposit, withdrawal and transfer appends one record: `(kind, account, counterparty, amount)`.

* deposit: `("deposit", account, "", x)`
* withdraw: `("withdraw", account, "", x)`
* transfer: `("transfer", from, to, x)`

`create` and `balance` never add a record. A rejected operation never adds a record.

---

## 2. Common structure (all three programs)

Each program has the same four layers plus a runner. Names are identical in all three programs (Python uses `LedgerTransaction` for the Rust `LedgerTxn`).

| Layer | Contents | Rust file | Python module |
|---|---|---|---|
| types | value types and errors: `Amount` and `AccountId` (Rust-Typed), `M` (Rust-Plain, Python), `AccountId` (Python), `BankError` | `src/types/*.rs` | `bank/types/*.py` |
| domain | `Account` (exactly two fields `id`, `balance`, **no default balance**) with `debit` and `credit`; `TransactionRecord` (`kind`, `account`, `counterparty`, `amount`) | `src/domain/*.rs` | `bank/domain/*.py` |
| repository | `Ledger` (the store) and `LedgerTxn` (its unit of work) | `src/repository/ledger.rs` | `bank/repository/ledger.py` |
| services | `FinancialService` with `create_account`, `balance`, `deposit`, `withdraw`, `transfer` | `src/services/financial_service.rs` | `bank/services/financial_service.py` |
| runner | CSV in, JSON lines out (Section 4) | `src/main.rs` | `bank/runner.py` |

### 2.1 Domain

* `Account.debit(x)` checks sufficient funds, then lowers the balance. `Account.credit(x)` checks the limit M, then raises the balance. Both report failure (Rust: `Result<(), BankError>`; Python: raise `BankError`). They are used by `withdraw` and `deposit` only, **not** by `transfer`.

### 2.2 Repository: ledger and unit of work

The `Ledger` holds the accounts in a map from id to `Account` and the records in a list. It offers:

* reads: `accounts()`, `records()`, `contains(id)`, and `find(id)`, which is the **only** account lookup in the program. It uses the "maybe" lookup (Rust: `self.accounts.get(id).ok_or(BankError::AccountNotFound)?`; Python: `self._accounts.get(id)` followed by an explicit `None` check that raises `AccountNotFound`). Never use `unwrap`, `expect`, or direct indexing.
* `begin()`, which opens a unit of work (`LedgerTxn`);
* `put(account)` and `append(record)`, the only writes to the store. They are called only by `LedgerTxn.commit` (Rust: `pub(crate)`).

The unit of work plays the role of a database transaction:

* `load(id)` returns a **copy** of the account (Rust: `clone`; Python: `dataclasses.replace`), via `find`;
* `save(account)` and `record(record)` stage changes;
* `commit()` applies all staged accounts with `put`, then all staged records with `append`.

A transaction that is not committed changes nothing. In Rust, `LedgerTxn<'a>` holds `&'a mut Ledger`, so no other access to the ledger is possible while it is open, and `commit(self)` consumes it, so it cannot be used after commit. The struct is marked `#[must_use]`. Python has no equivalent of these guarantees and **adds no runtime guard** for them (no "already committed" flag): code that is never exercised by valid inputs would distort the experiment.

### 2.3 Services

Every state-changing operation follows the same shape:

```
validate amount (Rust-Plain, Python; Rust-Typed: by the Amount type)
txn = ledger.begin()
load the account(s)                         (existence check, via find)
check the rule(s) / call debit or credit    (any failure returns early: txn is discarded)
apply the change to the loaded copies
txn.save(...) for each changed account
txn.record(...)
txn.commit()
```

`create_account` checks the id (Rust-Plain only; Rust-Typed and Python check it in `AccountId`), then `ledger.contains(id)` (else `DUPLICATE_ACCOUNT`), then saves `Account(id, balance = 0)` through a transaction and commits. `balance` calls `ledger.find(id)` and does not open a transaction.

For the transfer, each rule must be checked **exactly once**, inside `transfer` itself, before anything is staged. Do **not** call `debit` or `credit` from `transfer`: a duplicated check hides the effect of removing the first one, which would spoil the defect experiment. Order: amount valid → load source → load destination → `source.balance >= x` (else `INSUFFICIENT_FUNDS`) → destination limit (else `BALANCE_LIMIT_EXCEEDED`). In Rust-Typed, `let new_to = destination.balance.checked_add(x).ok_or(BankError::BalanceLimitExceeded)?;`. In Rust-Plain, `if x > M - destination.balance { return Err(...) }`. In Python, `if dst.balance + amount > M: raise ...`. Then one line lowers the source balance and one line sets (Rust-Typed: `= new_to`) or raises (Rust-Plain, Python: `+=`) the destination balance, both on the loaded copies; then save both, record, commit.

The assumption that the tools never transfer from an account to itself (A6) is kept: do not add a same-account check.

## 3. Program-specific rules

### 3.1 Rust-Typed (`rust/bank_typed`)

Crate attributes at the top of `lib.rs` **and** the runner `main.rs`:

```rust
#![forbid(unsafe_code)]
#![deny(unused_must_use)]
```

* **R1:** `pub struct Amount(u64);` with a **private** field. Its only constructor is `Amount::new(value: u64) -> Result<Amount, BankError>`, which returns `INVALID_AMOUNT` for 0. It has a `value()` getter. Balances are `u64`. Additions to a balance use `checked_add` and map `None` to `BALANCE_LIMIT_EXCEEDED`. A withdrawal first checks `balance >= x` (returning `INSUFFICIENT_FUNDS`), then uses plain subtraction.
* **R2:** `pub struct AccountId(String);` with a **private** field. Its only constructor is `AccountId::new(s: &str) -> Result<AccountId, BankError>`, which returns `INVALID_ACCOUNT_ID` for an empty string. It has an `as_str()` getter and no setter. It derives `Clone, PartialEq, Eq, Hash, Debug` and implements `Ord`, so it can be sorted for output.
* **R3:** every operation that can fail returns `Result<_, BankError>`, including `Account::debit` and `Account::credit`. Use `?`; never `let _ =`.
* **R4:** the ledger keeps accounts in `HashMap<AccountId, Account>`. The single lookup in `Ledger::find` uses `get` and `.ok_or(BankError::AccountNotFound)`. No `unwrap` or `expect` anywhere, including in the runner.
* **R6:** every state change goes through a `LedgerTxn` that borrows the ledger mutably and is consumed by `commit(self)`.
* **R5:** no `unsafe`. Use the standard library only, with **no external crates** (no serde, no csv crate). Write the CSV parsing and the JSON output by hand.

Service signatures take typed values, for example `deposit(&mut self, id: &AccountId, amount: Amount)`. The runner converts input text to typed values at the boundary (Section 4.1).

### 3.2 Rust-Plain (`rust/bank_plain`)

* Only `#![forbid(unsafe_code)]`. **No** `deny(unused_must_use)`; default lints only.
* No `Amount` or `AccountId` types. Amounts and balances are plain `u64`; ids are plain `String`.
* Every rule is an explicit check inside the operation:
  * `if amount == 0 { return Err(InvalidAmount) }`;
  * `if id.is_empty()` for create;
  * the limit check is written as `if amount > M - balance { return Err(BalanceLimitExceeded) }` followed by plain `+`, **not** `checked_add`;
  * the funds check is `if balance < amount` followed by plain `-`.
* Otherwise identical in structure to Rust-Typed: same `Account` with `debit`/`credit` returning `Result`, same service methods, same runner, same use of `?`, and no `unwrap`.
* Standard library only.

### 3.3 Python (`python/bank`)

* Python ≥ 3.11, standard library only.
* Type hints on every function, method and attribute. The code must pass `mypy --strict` with **zero** errors.
* `AccountId` is `@dataclass(frozen=True)` with one field `value: str`. Its `__post_init__` raises `InvalidAccountId` when the value is empty.
* `Account` is `@dataclass` (not frozen) with `id: AccountId` and `balance: int`, **no defaults**.
* Amounts and balances are `int`. Define `M: Final[int] = 2**64 - 1` and enforce it explicitly on every addition (`if balance + amount > M: raise BalanceLimitExceeded(...)`), because Python integers do not overflow.
* Amount validation is `if amount <= 0: raise InvalidAmount(...)`. This rejects zero and negative values in one check.
* Errors: `class BankError(Exception)` with a `code: str` attribute, and one subclass per error code (`InvalidAccountId`, `DuplicateAccount`, `AccountNotFound`, `InvalidAmount`, `InsufficientFunds`, `BalanceLimitExceeded`).
* The single lookup, in `Ledger.find`, is `acct = self._accounts.get(id)` then `if acct is None: raise AccountNotFound(...)`. Never use `self._accounts[id]` for a read.
* Every state change goes through a `LedgerTransaction`; `load` returns a copy made with `dataclasses.replace`.
* Multi-line docstrings and comment-only lines are not used in the package (single-line docstrings only), so that the mutation operators never act on non-code text.
* `mypy.ini` (or `pyproject.toml`) in `python/` with `strict = True`.

---

## 4. Runner interface (identical in all three programs)

### 4.1 Input

The runner is called with one argument, the path of a CSV file:

* Rust: `cargo run --release --bin bank_typed_runner -- ops.csv` (and `bank_plain_runner`)
* Python: `python -m bank.runner ops.csv` (run from `python/`)

The CSV has a header line `op,account,to,amount` and one operation per line. Fields are plain text without quotes or commas. Unused fields are empty.

```
op,account,to,amount
create,A001,,
deposit,A001,,5000
withdraw,A001,,1200
create,A002,,
transfer,A001,A002,800
balance,A002,,
deposit,A001,,-5
deposit,A009,,100
```

Parsing the amount at the boundary:

* The `amount` field is a decimal integer, which may be negative, between −2^63 and M inclusive.
* **Rust (both):** parse it as `i128`. If it is negative, the runner itself reports `INVALID_AMOUNT` for that operation, without calling the service and without changing state. Otherwise convert it to `u64` and call the service. In Rust-Typed, `Amount::new` then rejects 0. In Rust-Plain, the service rejects 0.
* **Python:** parse it with `int()` and pass it straight to the service, which rejects values ≤ 0.

The account id is the `account` (or `to`) field as given. An empty `account` field in `create` is the empty id. In Rust-Typed, a non-create operation naming an id that `AccountId::new` rejects (the empty string) cannot name an existing account, so report `ACCOUNT_NOT_FOUND`. For non-create operations, the tests never pass empty ids.

Because amount validation comes first (Section 1), a negative amount is reported as `INVALID_AMOUNT` even when the account also does not exist. All three programs therefore agree.

### 4.2 Output

For every operation, print exactly one line of JSON to standard output, with no spaces, keys in this order:

```json
{"step":0,"op":"create","status":"ok","error":null,"value":null,"accounts":[["A001",0]],"records":0,"last":null}
```

| Key | Meaning |
|---|---|
| `step` | 0-based index of the operation in the file |
| `op` | operation name as read |
| `status` | `"ok"` or `"error"` |
| `error` | error code string, or `null` |
| `value` | the balance for an accepted `balance` operation, otherwise `null` |
| `accounts` | all accounts **after** the operation, sorted by id (byte order), as `[id, balance]` pairs |
| `records` | number of records after the operation |
| `last` | the last record as `[kind, account, counterparty, amount]`, or `null` if there are none |

Balances and amounts are printed as plain integers (they can be as large as 18446744073709551615). Python must use `json.dumps(obj, separators=(",", ":"))` with the same key order. Rust must format the line by hand. Ids are printed as JSON strings. The tests use simple alphanumeric ids, so escaping is not needed.

* Exit code 0 when all lines have been processed.
* The program must **not** catch panics or unexpected exceptions. A panic (Rust) or an unhandled exception (Python) must end the program with a non-zero exit code. The harness counts that as the defect being caught.

---

## 5. Enforcement tags (required)

Every line that enforces a financial rule ends with a tag comment naming the invariant(s):

* Rust: `// [ENF:I1]` or `// [ENF:I1,I5]`
* Python: `# [ENF:I1]`

**Tagging rule:** tag a line if removing or weakening it would allow that invariant to be broken. A type definition that carries a rule is tagged the same way. To keep the three programs consistent, tag exactly these lines:

| What | Tag |
|---|---|
| every amount check (`== 0`, `<= 0`) and, in Rust-Typed, the `Amount` struct line and the zero check in `Amount::new` | I3 |
| every funds check (`balance < x`) and every limit check (`checked_add` line, `x > M - b`, `b + x > M`), plus the `M` constant line where one exists (Python, Rust-Plain) | I1 |
| every empty-id check, duplicate check and missing-account check (`ok_or(AccountNotFound)` line in `Ledger::find` in Rust, `is None` line in `Ledger.find` in Python), plus the `AccountId` struct line (Rust-Typed) and the `@dataclass(frozen=True)` line of `AccountId` (Python) | I4 |
| the two apply-phase lines of the transfer that change the source and destination balances | I2 |
| Rust only: the `pub struct LedgerTxn<'a>` line and the `pub fn commit(self)` line, because the borrow and the move they declare are what make a rejected or committed transaction unusable. Python has no corresponding line. | I5 |

Do not tag anything else: not the balance updates inside `debit`/`credit`, `load`/`save`/`record`/`commit` calls, the record pushes, parsing, output or the `#![...]` attributes. The negative-amount check in the Rust runners is input parsing at the boundary, so it gets no tag.

---

## 6. Project layout

```
bank-study/
  SPEC.md
  rust/
    Cargo.toml                       # workspace with members bank_typed, bank_plain
    bank_typed/src/                  # bank_plain/src/ has the same layout, without types/account_id.rs
      lib.rs                         # crate attributes, module declarations, re-exports
      main.rs                        # runner (bin bank_typed_runner)
      types/{mod,money,account_id,errors}.rs
      domain/{mod,account,record}.rs
      repository/{mod,ledger}.rs
      services/{mod,financial_service}.rs
  python/
    mypy.ini
    bank/
      __init__.py  runner.py
      types/{__init__,money,account_id,errors}.py
      domain/{__init__,account,record}.py
      repository/{__init__,ledger}.py
      services/{__init__,financial_service}.py
  harness/  data/  results/  archive/v1/
```

The Rust workspace must build with **default** profile settings. Do not set `overflow-checks` or any `[profile]` section. The experiment relies on the default behaviour: arithmetic overflow panics in debug and wraps in release.

## 7. Acceptance criteria

1. `cargo build` and `cargo build --release` succeed with **zero warnings** for both crates.
2. `cargo clippy` reports no errors (warnings may be discussed).
3. `mypy --strict bank` reports `Success: no issues found`.
4. All three runners, given the same CSV file, print **identical** output, byte for byte. Check this with the example in Section 4.1 and with your own files covering every row of the error table, the boundaries 0, 1, balance − 1, balance, balance + 1 and M, and a deposit that brings a balance exactly to M followed by a deposit of 1.
5. No `unwrap`, `expect`, `panic!`, `unsafe` or `[]` map indexing in the correct programs, and no external dependencies.
6. Every enforcement line is tagged (Section 5).
7. No features beyond this specification: no logging, configuration files, extra commands or same-account checks. Do not write unit tests inside the crates or the Python package. The frozen test suite lives in the external harness.

Expected output for the example in Section 4.1 (all three programs):

```
{"step":0,"op":"create","status":"ok","error":null,"value":null,"accounts":[["A001",0]],"records":0,"last":null}
{"step":1,"op":"deposit","status":"ok","error":null,"value":null,"accounts":[["A001",5000]],"records":1,"last":["deposit","A001","",5000]}
{"step":2,"op":"withdraw","status":"ok","error":null,"value":null,"accounts":[["A001",3800]],"records":2,"last":["withdraw","A001","",1200]}
{"step":3,"op":"create","status":"ok","error":null,"value":null,"accounts":[["A001",3800],["A002",0]],"records":2,"last":["withdraw","A001","",1200]}
{"step":4,"op":"transfer","status":"ok","error":null,"value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":5,"op":"balance","status":"ok","error":null,"value":800,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":6,"op":"deposit","status":"error","error":"INVALID_AMOUNT","value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":7,"op":"deposit","status":"error","error":"ACCOUNT_NOT_FOUND","value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
```

---

## 8. What comes later (for context only; do not build)

* A data generator will produce frozen test cases and 1,000 random sequences of 50 operations.
* An independent checker will verify the five invariants after every operation, and a comparison script will confirm that the three programs agree.
* A mutation script will create defective copies with seven kinds of change (removing a check, changing a comparison, changing arithmetic, deleting a state-update statement — including `save`, `record`, `commit`, `put` and `append` calls — ignoring a returned error, replacing error handling with direct access, swapping same-type arguments) in every file of the types, domain, repository and services layers. It will also add thirteen predefined defects: DS1 to DS10 from the original catalogue, and DS11 (write outside the unit of work), DS12 (commit despite a stored error) and DS13 (transaction used after commit), which reproduce patterns observed in an industrial Rust payments backend. Each copy is built and tested, and the result is recorded as caught at compile time, by mypy, by testing, or not caught.

This is why the structure above matters. For example, `Account` must have no default balance (defect DS10). `debit` must return a `Result` that the service must use (defect DS8). Lookups must go through `Option`/`None` (defect DS5). The transfer must check each rule exactly once (defects DS3, DS4 and DS9). If a rule were checked twice, removing one of the checks would change nothing, and the defect could never be observed. The unit of work must stage changes and apply them only at `commit` (DS11, DS12, DS13).
