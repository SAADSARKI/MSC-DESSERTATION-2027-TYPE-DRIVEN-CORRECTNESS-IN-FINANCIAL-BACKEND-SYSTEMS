# Bank Study — MSc Dissertation Implementation

Empirical comparison of Rust compile-time verification vs Python runtime validation in a financial backend prototype. MSc research, Crescent University Abeokuta.

**Dissertation:** "Type-Driven Correctness in Financial Backend Systems: An Empirical Evaluation of Compile-Time Verification Using Rust"
**Author:** Sa'ad Abdullahi Sarki, Crescent University Abeokuta

This repository contains the three correct baseline implementations, the external test harness, and all experimental data for the controlled mutation study described in the dissertation.

---

## Project Layout (version 2)

Version 2 keeps the external behaviour of version 1 (same CSV input, JSON output, error codes and order of checks, so the same data and oracle) and restructures each program into layers modelled on an industrial Rust payments backend, with an in-memory unit of work in the role of a database transaction. Version 1 (code, results and reports) is preserved in `archive/v1/`.

```
bank-study/
  SPEC.md                         # Authoritative specification (v2)
  README.md                       # This file
  rust/
    Cargo.toml                    # Workspace (members: bank_typed, bank_plain)
    bank_typed/src/               # Rust-Typed (newtypes, deny(unused_must_use))
      lib.rs  main.rs             #   crate root / runner (bank_typed_runner)
      types/      money.rs (Amount)  account_id.rs (AccountId)  errors.rs (BankError)
      domain/     account.rs (Account: debit, credit)  record.rs (TransactionRecord)
      repository/ ledger.rs (Ledger, LedgerTxn unit of work)
      services/   financial_service.rs (FinancialService)
    bank_plain/src/               # Rust-Plain: same layers, plain u64/String, explicit checks
  python/
    mypy.ini                      # strict = True
    bank/                         # Python: same layers (types, domain, repository, services) + runner.py
  harness/
    model.py  checker.py          # Reference oracle and independent invariant checker
    generate.py  validate_data.py # Data generator (seed 2026) and data-quality checks
    equivalence.py                # Runs all programs on all data, checks equivalence
    mutate.py                     # 7 mutation operators + defect scenarios DS1-DS13 (SCENARIOS table)
    run_defects.py                # Runs every mutant, classifies detection stage
    summarise.py                  # Builds the result tables -> results/summary.md
    plots.py                      # SVG figures -> results/figures/
    tests/                        # Self-tests of the harness (make test)
  data/                           # 10 frozen tests, 1000 sequences, manifest, reports
  results/                        # results_<program>.csv, mutants_<program>.json, logs,
                                  # summary.md, scenario_matrix.csv, operator_summary.csv,
                                  # enforcement_loc.csv, environment.json
  archive/v1/                     # Version 1 implementation and results
```

---

## Quick Start

```bash
make setup        # create .venv and install the pinned Python tools (requirements.txt)
make check        # build, clippy, mypy, harness self-tests, data validation, equivalence (~2 min)
make experiment   # mutants, defect runs for all three programs, summary, figures      (~4 min)
```

`make all` runs both. Results are written to `results/` (see `results/summary.md`, and the SVG figures in `results/figures/`); working copies and
their build output go to `runs/` (git-ignored). The same `make check` runs on GitHub Actions on every push;
the full experiment can be started from the Actions tab (workflow `ci`, "Run workflow") and its
`results/` folder is uploaded as an artifact.

## Prerequisites

### Rust

Install [rustup](https://rustup.rs). The exact compiler used for the reported results (**1.96.0**, with
Clippy) is pinned in `rust/rust-toolchain.toml`; rustup installs it on first use, or explicitly with
`rustup toolchain install 1.96.0 --profile minimal -c clippy`. The compiler version matters: a different
version can change error codes and lint behaviour, and so the compile-time classification of a defect.
No external crates are used.

### Python

Python ≥ 3.11 (results produced with 3.14.4). The harness tools are pinned in `requirements.txt`
(mypy 2.4.1); `make setup` installs them into `.venv`. To run scripts by hand, activate it first:

```bash
source .venv/bin/activate
```

---

## Building

```bash
cd rust

# Debug build (arithmetic overflow panics — correct baseline)
cargo build

# Release build (arithmetic overflow wraps — experiments overflow behaviour)
cargo build --release

# Zero-warning check
cargo clippy        # must report: Finished ... (no warnings)
```

Both builds must succeed with **zero warnings** (SPEC acceptance criterion 1 and 2).

---

## Running a Single Program

```bash
# Rust-Typed
./rust/target/debug/bank_typed_runner   data/tests/tc01_create_and_identity.csv
./rust/target/release/bank_typed_runner data/tests/tc01_create_and_identity.csv

# Rust-Plain
./rust/target/debug/bank_plain_runner   data/tests/tc01_create_and_identity.csv
./rust/target/release/bank_plain_runner data/tests/tc01_create_and_identity.csv

# Python (run from python/ directory)
cd python
python3 -m bank.runner ../data/tests/tc01_create_and_identity.csv
```

---

## Static Type Check (Python)

```bash
cd python
source ../.venv/bin/activate   # activate the venv created above
mypy --strict bank             # must print: Success: no issues found
```

---

## Verifying Equivalence

Runs all three programs on all 10 frozen test cases and all 1000 random sequences, checks each output against the oracle, and verifies no invariant is broken.

```bash
cd harness
source ../.venv/bin/activate
python3 equivalence.py
```

Expected output for every program:

```
"accepted": true, "crashes": 0, "output_differences": 0, "invariant_violations": 0
```

The report is written to `data/equivalence_report.json`.

---

## Validating Test Data

```bash
cd harness
source ../.venv/bin/activate
python3 validate_data.py
```

Checks reproducibility, boundary coverage, invariant coverage and the checker's own self-test. Report written to `data/validation_report.json`.

---

## Running the Defect Experiment and Building the Summary

```bash
cd harness
source ../.venv/bin/activate

# One program at a time (each takes ~2 minutes)
python3 run_defects.py rust_typed
python3 run_defects.py rust_plain
python3 run_defects.py python

# Chapter 4 tables (detection matrix, operator outcomes, enforcement LOC, tool versions)
python3 summarise.py               # -> results/summary.md and CSVs
```

Results are written to `results/results_<program>.csv`. Each row is one (mutant, profile) pair with columns:

| Column | Meaning |
|---|---|
| `result` | `compile_time`, `static_check`, `testing`, or `not_caught` |
| `configuration` | Rust-Typed, Rust-Plain, Python-Runtime, Python-Static |
| `operator` / `mutant` | mutation kind and ID |
| `before` / `after` | original and mutated text |
| `detail` | first file and step where detection occurred |

---

## Quick Verification (Smoke Test)

Run this after any change to confirm nothing is broken:

```bash
ROOT=$(pwd)  # run from bank-study/

# 1. Build
(cd rust && cargo build --release 2>&1 | tail -1)

# 2. All 10 frozen test cases — all three programs
for f in data/tests/tc*.csv; do
  base="${f%.csv}"
  out_t=$(rust/target/release/bank_typed_runner "$f")
  out_p=$(rust/target/release/bank_plain_runner "$f")
  out_py=$(cd python && python3 -m bank.runner "../$f")
  exp=$(cat "${base}.expected.jsonl")
  if [ "$out_t" = "$exp" ] && [ "$out_p" = "$exp" ] && [ "$out_py" = "$exp" ]; then
    echo "PASS $(basename $f)"
  else
    echo "FAIL $(basename $f)"
  fi
done
```

Expected: 10 × PASS, no FAIL.

---

## Known Status (version 2, run of 2026-11-23)

Toolchain: rustc 1.96.0, Python 3.14.4, mypy 2.4.1 (recorded in `results/environment.json`).

| Check | Status |
|---|---|
| `cargo build` (debug + release), `cargo clippy` | ✅ Zero warnings |
| `mypy --strict bank` | ✅ Success: no issues found (13 source files) |
| Equivalence, 1,010 files / 50,196 operations, 5 builds | ✅ 0 crashes, 0 output differences, 0 invariant violations |
| Defect experiment — Rust-Typed | ✅ 48 operator mutants + 13 scenarios, debug and release (122 rows) |
| Defect experiment — Rust-Plain | ✅ 56 operator mutants + 13 scenarios, debug and release (138 rows) |
| Defect experiment — Python | ✅ 59 operator mutants + 13 scenarios, Runtime and Static (144 rows) |
| Mutants not caught / equivalent mutants | None |

See `results/summary.md` for the full tables.
