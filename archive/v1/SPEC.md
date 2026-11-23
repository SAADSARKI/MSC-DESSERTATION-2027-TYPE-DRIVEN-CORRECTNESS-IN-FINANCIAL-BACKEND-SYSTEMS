# Build Specification: Financial Backend in Rust and Python

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

Each program has:

1. **A core library** with these parts:
   * `Account`, with exactly two fields, `id` and `balance`. There is **no default value** for `balance`. Account creation must pass `balance` explicitly (as 0). This matters for a later defect.
   * `Account.debit(x)` and `Account.credit(x)`, which apply a change to one account and report failure (Rust: return `Result<(), BankError>`; Python: raise `BankError`). `debit` checks sufficient funds. `credit` checks the limit M. They are used by `withdraw` and `deposit` only, **not** by `transfer` (see below).
   * `TransactionRecord`, with fields `kind`, `account`, `counterparty`, `amount`.
   * `BankError`, with one variant per error code.
   * `FinancialService` (Rust: struct; Python: class), which holds the accounts in a map from id to `Account` and the records in a list. It provides `create_account`, `balance`, `deposit`, `withdraw` and `transfer`. The service methods call `debit` and `credit` and propagate their errors (Rust: `?`).
2. **A runner** (a command-line program) that reads operations from a CSV file, applies them to one new `FinancialService`, and prints one JSON line per operation (Section 4).

The account map is looked up with a method that returns "maybe" (Rust: `HashMap::get` / `get_mut` returning `Option`, converted to `Result` with `ok_or`; Python: `dict.get(...)` followed by an explicit `None` check that raises). **Never** use `unwrap`, `expect`, or direct indexing (`map[key]`) in the correct programs. Direct access appears only in a later defect.

For the transfer, each rule must be checked **exactly once**, inside `transfer` itself, before anything changes. Do **not** call `debit` or `credit` from `transfer`: they would check the same rules a second time, and a duplicated check hides the effect of removing the first one, which would spoil the defect experiment. The transfer is written in two phases:

1. **Check phase:** amount valid → source exists → destination exists → `balance(from) >= x` (else `INSUFFICIENT_FUNDS`) → new destination balance within M (else `BALANCE_LIMIT_EXCEEDED`). In Rust-Typed, compute `let new_to = to_balance.checked_add(x).ok_or(BankError::BalanceLimitExceeded)?;`. In Rust-Plain, write `if x > M - to_balance { return Err(...) }`. In Python, write `if dst.balance + amount > M: raise ...`.
2. **Apply phase:** one line that lowers the source balance by x, one line that sets or raises the destination balance, then push the record. Rust-Typed sets the destination to `new_to`; Rust-Plain and Python add x with plain `+`.

The apply phase cannot fail, so a transfer is never left with only one side applied.

Deposit and withdraw do their amount and existence checks in the service, then call `credit` or `debit` and propagate the result, then push the record.

---

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
* **R4:** accounts are kept in `HashMap<AccountId, Account>`. Lookups use `get`/`get_mut` and `.ok_or(BankError::AccountNotFound)`. No `unwrap` or `expect` anywhere, including in the runner.
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
* Lookup is `acct = self._accounts.get(id)` then `if acct is None: raise AccountNotFound(...)`. Never use `self._accounts[id]` for a read.
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
| every empty-id check, duplicate check and missing-account check (`ok_or(AccountNotFound)` line in Rust, `is None` line in Python), plus the `AccountId` struct line (Rust-Typed) and the `@dataclass(frozen=True)` line of `AccountId` (Python) | I4 |
| the two apply-phase lines of the transfer that change the source and destination balances | I2 |

Do not tag anything else: not the balance updates inside `debit`/`credit`, the record pushes, parsing, output or the `#![...]` attributes. The negative-amount check in the Rust runners is input parsing at the boundary, so it gets no tag.

---

## 6. Project layout

```
bank-study/
  SPEC.md
  rust/
    Cargo.toml                 # workspace with members bank_typed, bank_plain
    bank_typed/
      Cargo.toml               # [[bin]] name = "bank_typed_runner", path = "src/main.rs"
      src/lib.rs
      src/main.rs
    bank_plain/
      Cargo.toml               # [[bin]] name = "bank_plain_runner"
      src/lib.rs
      src/main.rs
  python/
    mypy.ini
    bank/
      __init__.py
      core.py                  # AccountId, Account, TransactionRecord, errors, FinancialService
      runner.py                # CSV in, JSON lines out
  harness/                     # NOT part of this task
  data/                        # NOT part of this task
```

The Rust workspace must build with **default** profile settings. Do not set `overflow-checks` or any `[profile]` section. The experiment relies on the default behaviour: arithmetic overflow panics in debug and wraps in release.

---

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
* A mutation script will create defective copies with seven kinds of change (removing a check, changing a comparison, changing arithmetic, deleting a state-update statement, ignoring a returned error, replacing error handling with direct access, swapping same-type arguments). It will also add ten predefined defects (DS1 to DS10). Each copy is built and tested, and the result is recorded as caught at compile time, by mypy, by testing, or not caught.

This is why the structure above matters. For example, `Account` must have no default balance (defect DS10). `debit` must return a `Result` that the service must use (defect DS8). Lookups must go through `Option`/`None` (defect DS5). The transfer must check each rule exactly once (defects DS3, DS4 and DS9). If a rule were checked twice, removing one of the checks would change nothing, and the defect could never be observed.
