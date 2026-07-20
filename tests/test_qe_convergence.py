#!/usr/bin/env python3

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from qe_convergence import classify_qe_convergence


class TestQEConvergenceClassification(unittest.TestCase):
    def classify(self, input_text: str, output_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "pw.in"
            input_path.write_text(input_text)
            return classify_qe_convergence(output_text, input_path)

    def test_strict_convergence(self):
        result = self.classify(
            """
&ELECTRONS
  electron_maxstep = 100,
  scf_must_converge = .TRUE.,
  conv_thr = 1.0d-6,
/
""",
            """
iteration # 15
estimated scf accuracy < 9.1D-7 Ry
convergence has been achieved in 15 iterations
JOB DONE.
""",
        )
        self.assertEqual(result["convergence_status"], "strict_converged")
        self.assertTrue(result["strict_scf_converged"])
        self.assertFalse(result["forced_accept"])

    def test_maxstep_forced_accept(self):
        result = self.classify(
            """
&ELECTRONS
  electron_maxstep = 4,
  scf_must_converge = .FALSE.,
  conv_thr = 1.0d-6,
/
""",
            """
iteration # 1
iteration # 2
iteration # 3
iteration # 4
estimated scf accuracy < 9.96531854 Ry
convergence has been achieved in 4 iterations
JOB DONE.
""",
        )
        self.assertEqual(
            result["convergence_status"],
            "maxstep_forced_accept",
        )
        self.assertFalse(result["strict_scf_converged"])
        self.assertTrue(result["forced_accept"])
        self.assertTrue(result["reached_electron_maxstep"])

    def test_explicit_non_convergence(self):
        result = self.classify(
            """
&ELECTRONS
  electron_maxstep = 5,
  conv_thr = 1.0d-8,
/
""",
            """
iteration # 5
estimated scf accuracy < 105.89 Ry
convergence NOT achieved after 5 iterations: stopping
JOB DONE.
""",
        )
        self.assertEqual(result["convergence_status"], "not_converged")
        self.assertFalse(result["strict_scf_converged"])
        self.assertFalse(result["forced_accept"])


if __name__ == "__main__":
    unittest.main()
