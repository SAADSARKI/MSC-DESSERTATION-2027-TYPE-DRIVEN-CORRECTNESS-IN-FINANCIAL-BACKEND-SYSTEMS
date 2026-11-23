"""Defect-runner safeguards and data integrity."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

from run_defects import PYTHON_RUNNER
from summarise import stage_of

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class BytecodeCacheTest(unittest.TestCase):
    """Regression test for the stale-bytecode bug found on 2026-11-23.

    Python validates a cached .pyc only by the source's mtime (whole seconds)
    and size. Two same-sized mutants of one file written within one second
    therefore run the *earlier* mutant unless bytecode caching is disabled.
    """

    def run_twice(self, flags: list[str]) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as d:
            pkg = os.path.join(d, "pkg")
            os.makedirs(pkg)
            open(os.path.join(pkg, "__init__.py"), "w").close()
            mod = os.path.join(pkg, "m.py")
            outs = []
            for value in ("1", "2"):                  # same size, same mtime
                with open(mod, "w") as f:
                    f.write(f"print({value})\n")
                os.utime(mod, (1_700_000_000, 1_700_000_000))
                env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
                p = subprocess.run([sys.executable, *flags, "-m", "pkg.m"], cwd=d, env=env,
                                   capture_output=True, text=True, check=True)
                outs.append(p.stdout.strip())
            return outs[0], outs[1]

    def test_the_hazard_is_real_without_B(self) -> None:
        self.assertEqual(self.run_twice([]), ("1", "1"))     # second run executes stale code

    def test_B_runs_the_current_source(self) -> None:
        self.assertEqual(self.run_twice(["-B"]), ("1", "2"))

    def test_runner_command_uses_B(self) -> None:
        self.assertIn("-B", PYTHON_RUNNER)
        self.assertLess(PYTHON_RUNNER.index("-B"), PYTHON_RUNNER.index("-m"))


class StageOfTest(unittest.TestCase):
    def test_same_result_in_both_profiles(self) -> None:
        rows = [{"profile": "debug", "result": "testing"}, {"profile": "release", "result": "testing"}]
        self.assertEqual(stage_of(rows), "test")

    def test_profiles_that_differ_are_both_shown(self) -> None:
        rows = [{"profile": "debug", "result": "testing"}, {"profile": "release", "result": "not_caught"}]
        self.assertEqual(stage_of(rows), "test (debug) / MISSED (release)")


class DataIntegrityTest(unittest.TestCase):
    def test_every_data_file_matches_the_manifest(self) -> None:
        with open(os.path.join(ROOT, "data", "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        # 1,000 random sequences + 10 frozen test cases with their expected outputs
        self.assertEqual(len(manifest["files"]), 1000 + 10 * 2)
        for rel, digest in manifest["files"].items():
            with open(os.path.join(ROOT, "data", rel), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest, rel)


if __name__ == "__main__":
    unittest.main()
