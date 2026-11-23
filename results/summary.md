# Experiment summary

## Environment

| tool | version |
|---|---|
| rustc | rustc 1.96.0 (ac68faa20 2026-05-25) |
| cargo | cargo 1.96.0 (30a34c682 2026-05-25) |
| python | 3.14.4 |
| mypy | mypy 2.4.1 (compiled: yes) |
| os | Linux 7.0.0-44-generic |

## Defect scenarios: detection stage (RQ1, RQ2)

compile = rejected by rustc; mypy = rejected by mypy --strict; test = revealed by the frozen tests or random sequences; MISSED = passed every test.

| DS | scenario | invariant | origin | Rust-Typed | Rust-Plain | Python-Runtime | Python-Static |
|---|---|---|---|---|---|---|---|
| DS1 | Withdrawal without funds check | I1 | catalogue | test | test | test | test |
| DS2 | Zero amount accepted | I3 | catalogue | test | test | test | test |
| DS3 | Incomplete transfer | I2 | catalogue | test | test | test | test |
| DS4 | Transfer without funds check | I1 | catalogue | test | test | test | test |
| DS5 | Unchecked account lookup | I4 | catalogue | test | test | test | test |
| DS6 | Negative amount at the boundary | I3 | catalogue | compile | compile | test | test |
| DS7 | Duplicate account identifier | I4 | catalogue | test | test | test | test |
| DS8 | Ignored failure result | I1,I5 | catalogue | compile | test | test | test |
| DS9 | Numeric overflow on deposit | I1 | catalogue | test | test | test | test |
| DS10 | Account used before initialisation | I1,I4 | catalogue | compile | compile | test | mypy |
| DS11 | Write outside the unit of work | I2,I5 | industrial | compile | compile | test | test |
| DS12 | Commit despite a stored error | I5 | industrial | test | test | test | test |
| DS13 | Transaction used after commit | I5 | industrial | compile | compile | test | test |

## Operator mutants: outcomes (debug profile for Rust)

| operator | Rust-Typed (compile/mypy/test/missed) | Rust-Plain (compile/mypy/test/missed) | Python-Runtime (compile/mypy/test/missed) | Python-Static (compile/mypy/test/missed) |
|---|---|---|---|---|
| change_arithmetic | 0/0/4/0 | 0/0/6/0 | 0/0/7/0 | 0/0/7/0 |
| change_comparison | 0/0/3/0 | 0/0/7/0 | 0/0/8/0 | 0/0/8/0 |
| delete_statement | 0/0/22/0 | 0/0/22/0 | 0/0/22/0 | 0/0/22/0 |
| direct_access | 0/0/1/0 | 0/0/1/0 | 0/0/1/0 | 0/0/1/0 |
| ignore_error | 2/0/0/0 | 0/0/2/0 | 0/0/2/0 | 0/0/2/0 |
| remove_check | 0/0/7/0 | 0/0/9/0 | 0/0/10/0 | 0/1/9/0 |
| swap_arguments | 2/0/7/0 | 2/0/7/0 | 0/0/9/0 | 0/0/9/0 |
| TOTAL | 4/0/44/0 | 2/0/54/0 | 0/0/59/0 | 0/1/58/0 |

## Mutants whose outcome differs between debug and release

None.

## Mutants not caught

None.

## Enforcement code volume (RQ3)

Lines carrying an [ENF:Ix] tag (SPEC Section 5). A line tagged with two invariants counts once per invariant and once in the total.

| program | I1 | I2 | I3 | I4 | I5 | tagged lines |
|---|---|---|---|---|---|---|
| rust_typed | 4 | 2 | 2 | 4 | 2 | 14 |
| rust_plain | 5 | 2 | 3 | 3 | 2 | 15 |
| python | 5 | 2 | 3 | 4 | 0 | 14 |

### Where each invariant is enforced (files containing tagged lines)

- **rust_typed**: I1: account.rs, financial_service.rs; I2: financial_service.rs; I3: money.rs; I4: account_id.rs, financial_service.rs, ledger.rs; I5: ledger.rs
- **rust_plain**: I1: account.rs, financial_service.rs, money.rs; I2: financial_service.rs; I3: financial_service.rs; I4: financial_service.rs, ledger.rs; I5: ledger.rs
- **python**: I1: account.py, financial_service.py, money.py; I2: financial_service.py; I3: financial_service.py; I4: account_id.py, financial_service.py, ledger.py

### Code lines per layer (non-blank, non-comment)

| program | crate root | types | domain | repository | services | runner | total |
|---|---|---|---|---|---|---|---|
| rust_typed | 13 | 59 | 31 | 72 | 81 | 129 | 385 |
| rust_plain | 11 | 24 | 28 | 71 | 84 | 116 | 334 |
| python | 0 | 32 | 23 | 43 | 60 | 59 | 217 |

