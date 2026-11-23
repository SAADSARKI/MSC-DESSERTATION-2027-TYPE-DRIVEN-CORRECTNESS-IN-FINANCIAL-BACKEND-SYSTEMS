"""The reference model (oracle) and the invariant checker."""
from __future__ import annotations

import glob
import json
import os
import unittest

from checker import check_run
from model import Op, read_csv, run
from validate_data import checker_self_test

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TESTS = sorted(glob.glob(os.path.join(ROOT, "data", "tests", "*.csv")))
SEQS = sorted(glob.glob(os.path.join(ROOT, "data", "sequences", "*.csv")))

# SPEC.md Section 4.1 example and its expected output (SPEC Section 7).
SPEC_OPS = [Op("create", "A001", "", None), Op("deposit", "A001", "", 5000), Op("withdraw", "A001", "", 1200),
            Op("create", "A002", "", None), Op("transfer", "A001", "A002", 800), Op("balance", "A002", "", None),
            Op("deposit", "A001", "", -5), Op("deposit", "A009", "", 100)]
SPEC_EXPECTED = """\
{"step":0,"op":"create","status":"ok","error":null,"value":null,"accounts":[["A001",0]],"records":0,"last":null}
{"step":1,"op":"deposit","status":"ok","error":null,"value":null,"accounts":[["A001",5000]],"records":1,"last":["deposit","A001","",5000]}
{"step":2,"op":"withdraw","status":"ok","error":null,"value":null,"accounts":[["A001",3800]],"records":2,"last":["withdraw","A001","",1200]}
{"step":3,"op":"create","status":"ok","error":null,"value":null,"accounts":[["A001",3800],["A002",0]],"records":2,"last":["withdraw","A001","",1200]}
{"step":4,"op":"transfer","status":"ok","error":null,"value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":5,"op":"balance","status":"ok","error":null,"value":800,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":6,"op":"deposit","status":"error","error":"INVALID_AMOUNT","value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}
{"step":7,"op":"deposit","status":"error","error":"ACCOUNT_NOT_FOUND","value":null,"accounts":[["A001",3000],["A002",800]],"records":3,"last":["transfer","A001","A002",800]}""".splitlines()


class OracleTest(unittest.TestCase):
    def test_spec_example(self) -> None:
        self.assertEqual(run(SPEC_OPS), SPEC_EXPECTED)

    def test_frozen_expected_outputs_come_from_the_oracle(self) -> None:
        self.assertEqual(len(TESTS), 10)
        for f in TESTS:
            with self.subTest(file=os.path.basename(f)):
                with open(f.replace(".csv", ".expected.jsonl"), encoding="utf-8") as fh:
                    expected = fh.read().splitlines()
                self.assertEqual(run(read_csv(f)), expected)


class CheckerTest(unittest.TestCase):
    def test_no_violation_on_correct_output(self) -> None:
        for f in TESTS + SEQS[:50]:
            ops = read_csv(f)
            with self.subTest(file=os.path.basename(f)):
                self.assertEqual(check_run(ops, run(ops)), [])

    def test_each_kind_of_defect_is_flagged_with_its_invariant(self) -> None:
        expected = {
            "negative balance after withdrawal (DS1-like)": ["I1"],
            "accepted zero deposit (DS2-like)": ["I3"],
            "transfer without credit (DS3-like)": ["I2", "I5"],
            "accepted operation on missing account (DS5-like)": ["I4"],
            "duplicate create accepted (DS7-like)": ["I4"],
            "rejected withdrawal still recorded (DS8-like)": ["I5"],
            "balance above M (DS9-like)": ["I1"],
            "deposit applied with wrong amount": ["I5"],
        }
        self.assertEqual(checker_self_test(), expected)

    def test_rejected_operation_that_changes_state_breaks_I5(self) -> None:
        ops = [Op("create", "A", "", None), Op("withdraw", "A", "", 10)]
        good = run(ops)
        bad = json.loads(good[1])
        bad["records"] = 1
        bad["last"] = ["withdraw", "A", "", 10]
        self.assertEqual(check_run(ops, [good[0], json.dumps(bad, separators=(",", ":"))]), [(1, ["I5"])])


if __name__ == "__main__":
    unittest.main()
