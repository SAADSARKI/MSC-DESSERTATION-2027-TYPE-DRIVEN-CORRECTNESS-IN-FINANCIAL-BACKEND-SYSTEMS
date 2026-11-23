# Bank Study — MSc Dissertation Implementation

**Dissertation:** "Type-Driven Correctness in Financial Backend Systems: An Empirical Evaluation of Compile-Time Verification Using Rust"
**Author:** Sa'ad Abdullahi Sarki, Crescent University Abeokuta

This repository contains the three correct baseline implementations, the external test harness, and all experimental data for the controlled mutation study described in the dissertation.

---

## Project Layout

```
bank-study/
  SPEC.md                   # Authoritative specification — do not change
  README.md                 # This file
  rust/
    Cargo.toml              # Workspace (members: bank_typed, bank_plain)
    bank_typed/src/lib.rs   # Rust-Typed core library
    bank_typed/src/main.rs  # Rust-Typed runner
    bank_plain/src/lib.rs   # Rust-Plain core library
    bank_plain/src/main.rs  # Rust-Plain runner
  python/
    mypy.ini                # strict = True
    bank/core.py            # Python core library
    bank/runner.py          # Python runner
  harness/
    model.py                # Reference oracle (not under test)
    checker.py              # Independent invariant checker
    generate.py             # Data generator (seed 2026)
    validate_data.py        # Data quality verification
    equivalence.py          # Runs all programs on all data, checks equivalence
    mutate.py               # Generates mutants (operator + DS1–DS10)
    run_defects.py          # Runs every mutant, classifies defect detection
  data/
    tests/                  # 10 frozen CSV test cases + expected .jsonl outputs
    sequences/              # 1000 random sequences of 50 operations (seq_0000–seq_0999)
    manifest.json           # Seed, counts, SHA-256 hashes of every data file
    equivalence_report.json # Result of equivalence.py (all programs accepted)
    validation_report.json  # Result of validate_data.py
  results/
    results_rust_typed.csv  # Defect detection results for Rust-Typed
    results_rust_plain.csv  # Defect detection results for Rust-Plain
    results_python.csv      # Defect detection results for Python
    mutants_rust_typed.json # All mutant descriptors for Rust-Typed
    mutants_rust_plain.json # All mutant descriptors for Rust-Plain
    mutants_python.json     # All mutant descriptors for Python
    log_rust_typed.txt      # run_defects.py console output for Rust-Typed
    log_rust_plain.txt      # run_defects.py console output for Rust-Plain
    log_python.txt          # run_defects.py console output for Python
```

---

## Prerequisites

### Rust

```bash
# Install via rustup if not present
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update stable
```

Requires Rust ≥ 1.70 (uses `let-else`, `?` in closures, `u64::MAX`). No external crates.

### Python

Python ≥ 3.11 required (uses `str | None` union syntax in type hints).

```bash
# Create a virtual environment and install mypy
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install mypy
```

The harness scripts (`equivalence.py`, `run_defects.py`) must be run from inside the venv.

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

## Running the Defect Experiment

```bash
cd harness
source ../.venv/bin/activate

# One program at a time (each takes ~2 minutes)
python3 run_defects.py rust_typed
python3 run_defects.py rust_plain
python3 run_defects.py python
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

## Known Status

| Check | Status |
|---|---|
| `cargo build` (debug + release) | ✅ Zero warnings |
| `cargo clippy` | ✅ Zero warnings |
| `mypy --strict bank` | ✅ Success: no issues found (requires venv) |
| All 10 frozen test cases | ✅ All three programs pass |
| 1000 random sequences — equivalence | ✅ All three programs agree, 0 invariant violations |
| Defect experiment — Rust-Typed | ✅ 100 rows, all defects detected or classified |
| Defect experiment — Rust-Plain | ✅ 116 rows, all defects detected or classified |
| Defect experiment — Python | ✅ 126 rows (Runtime + Static), all defects detected or classified |

---

## Acceptance Criteria Checklist (SPEC Section 7)

1. ✅ `cargo build` and `cargo build --release` succeed with zero warnings
2. ✅ `cargo clippy` reports no errors (zero warnings after `Default` impl fix)
3. ✅ `mypy --strict bank` reports `Success: no issues found`
4. ✅ All three runners produce identical byte-for-byte output on all test inputs
5. ✅ No `unwrap`, `expect`, `panic!`, `unsafe`, or `[]` map indexing in correct programs
6. ✅ Every enforcement line is tagged (`[ENF:I1]` through `[ENF:I4]`)
7. ✅ No features beyond the specification
