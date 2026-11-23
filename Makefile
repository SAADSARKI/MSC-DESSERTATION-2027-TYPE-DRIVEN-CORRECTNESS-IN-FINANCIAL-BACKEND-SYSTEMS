# Reproducible pipeline for the bank-study experiment.
#
#   make setup        create .venv and install the pinned Python tools
#   make check        build + lint + data validation + equivalence   (~2 min)
#   make test         self-tests of the harness (oracle, checker, mutation tool)
#   make experiment   mutants + defect runs for all programs + summary + figures (~4 min)
#   make all          check, then experiment
#
# The Rust compiler version is pinned in rust/rust-toolchain.toml and is
# installed automatically by rustup on first use.
# All recipes use relative paths, because the project path may contain spaces.

# Use the project virtual environment when it exists (CI installs into the
# runner's Python instead and leaves .venv absent).
VENV_BIN := .venv/bin
# The venv's bin directory is put first on PATH (an absolute path: Python 3.14
# warns when a venv interpreter is started through a relative path).
ifneq ($(wildcard $(VENV_BIN)/python),)
export PATH := $(CURDIR)/$(VENV_BIN):$(PATH)
endif
PY := python3
MYPY := mypy

PROGRAMS := rust_typed rust_plain python

.PHONY: all setup check test build lint validate equivalence experiment mutants defects summary figures clean

all: check experiment

setup:
	python3 -m venv .venv
	.venv/bin/pip install --quiet -r requirements.txt

check: build lint test validate equivalence

build:
	cd rust && cargo build --quiet && cargo build --quiet --release

test:
	cd harness && $(PY) -B -m unittest discover -s tests -t . -q

lint:
	cd rust && cargo clippy --quiet --all-targets -- -D warnings
	cd python && $(MYPY) --strict bank

validate:
	cd harness && $(PY) validate_data.py > /dev/null && echo "data validation: OK"

equivalence:
	cd harness && $(PY) equivalence.py

experiment: mutants defects summary figures

mutants:
	cd harness && $(PY) mutate.py

defects:
	@for p in $(PROGRAMS); do \
		echo "== defect runs: $$p"; \
		(cd harness && $(PY) run_defects.py $$p > ../results/log_$$p.txt 2>&1) || { tail -20 results/log_$$p.txt; exit 1; }; \
		tail -n 1 results/log_$$p.txt; \
	done

summary:
	cd harness && $(PY) summarise.py > /dev/null && echo "summary: results/summary.md"

figures:
	cd harness && $(PY) plots.py

clean:
	rm -rf runs rust/target harness/__pycache__ python/.mypy_cache
	find python -name __pycache__ -type d -prune -exec rm -rf {} +
