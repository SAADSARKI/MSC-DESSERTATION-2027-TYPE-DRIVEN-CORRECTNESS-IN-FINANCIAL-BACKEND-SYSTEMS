"""The mutation tool: the defect instrument must not change silently.

If a change to the programs or to mutate.py alters the set of mutants, these
tests fail and the expected counts below must be updated on purpose, together
with a new run of the experiment.
"""
from __future__ import annotations

import ast
import difflib
import os
import unittest
from collections import Counter

from mutate import DS, PROGRAMS, SCENARIOS, generate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

EXPECTED_OPERATOR_COUNTS = {
    "rust_typed": {"remove_check": 7, "change_comparison": 3, "change_arithmetic": 4, "delete_statement": 22,
                   "direct_access": 1, "ignore_error": 2, "swap_arguments": 9},
    "rust_plain": {"remove_check": 9, "change_comparison": 7, "change_arithmetic": 6, "delete_statement": 22,
                   "direct_access": 1, "ignore_error": 2, "swap_arguments": 9},
    "python": {"remove_check": 10, "change_comparison": 8, "change_arithmetic": 7, "delete_statement": 22,
               "direct_access": 1, "ignore_error": 2, "swap_arguments": 9},
}

MUTANTS = {p: generate(p) for p in PROGRAMS}


def original(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class MutantSetTest(unittest.TestCase):
    def test_operator_counts_are_unchanged(self) -> None:
        for p, ms in MUTANTS.items():
            with self.subTest(program=p):
                got = dict(Counter(m.operator for m in ms if m.kind == "operator"))
                self.assertEqual(got, EXPECTED_OPERATOR_COUNTS[p])

    def test_every_program_has_all_thirteen_scenarios(self) -> None:
        self.assertEqual(list(SCENARIOS), [f"DS{i}" for i in range(1, 14)])
        for p, ms in MUTANTS.items():
            with self.subTest(program=p):
                self.assertEqual([m.operator for m in ms if m.kind == "scenario"], list(SCENARIOS))
                self.assertEqual([d[0] for d in DS[p]], list(SCENARIOS))

    def test_mutant_ids_are_unique(self) -> None:
        for p, ms in MUTANTS.items():
            ids = [m.id for m in ms]
            self.assertEqual(len(ids), len(set(ids)), p)

    def test_runner_is_mutated_only_by_scenarios(self) -> None:
        for p, ms in MUTANTS.items():
            runner = PROGRAMS[p]["runner"]
            for m in ms:
                if m.file == runner:
                    self.assertEqual(m.kind, "scenario", m.id)


class MutantShapeTest(unittest.TestCase):
    def test_each_mutant_changes_its_file(self) -> None:
        for p, ms in MUTANTS.items():
            for m in ms:
                with self.subTest(mutant=m.id):
                    self.assertNotEqual(m.source, original(m.file))

    def test_operator_mutants_change_one_place(self) -> None:
        """One contiguous change, plus at most an added import line (Python)."""
        for p, ms in MUTANTS.items():
            for m in ms:
                if m.kind != "operator":
                    continue
                with self.subTest(mutant=m.id):
                    sm = difflib.SequenceMatcher(None, original(m.file).split("\n"), m.source.split("\n"))
                    changes = [op for op in sm.get_opcodes() if op[0] != "equal"]
                    imports = [op for op in changes if op[0] == "insert"
                               and all(ln.startswith("from bank.") for ln in m.source.split("\n")[op[3]:op[4]])]
                    self.assertEqual(len(changes) - len(imports), 1)

    def test_python_mutants_are_valid_syntax(self) -> None:
        """A mutant must fail because of its defect, never because it is not Python."""
        for m in MUTANTS["python"]:
            with self.subTest(mutant=m.id):
                ast.parse(m.source)

    def test_python_mutants_import_the_names_they_use(self) -> None:
        for m in MUTANTS["python"]:
            if "BankError" in m.source:
                with self.subTest(mutant=m.id):
                    self.assertRegex(m.source, r"import BankError|BankError,|\bclass BankError\b")

    def test_rust_delete_leaves_empty_statement_python_leaves_pass(self) -> None:
        for p, ms in MUTANTS.items():
            for m in ms:
                if m.operator == "delete_statement":
                    with self.subTest(mutant=m.id):
                        self.assertEqual(m.after, "" if PROGRAMS[p]["lang"] == "rust" else "pass")


if __name__ == "__main__":
    unittest.main()
