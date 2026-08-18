from __future__ import annotations

import json
import math
import unittest

from governai.experiment import run_experiment, stable_assignment


class ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.units = [f"ACC-{index:05d}" for index in range(1, 321)]

    def test_assignment_is_stable_and_order_independent(self) -> None:
        assignments = {unit: stable_assignment(unit) for unit in self.units}
        repeated = {unit: stable_assignment(unit) for unit in reversed(self.units)}
        self.assertEqual(assignments, repeated)
        self.assertEqual(sum(arm == "treatment" for arm in assignments.values()), 148)

        forward = run_experiment(self.units)
        reverse = run_experiment(reversed(self.units))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            forward["design"]["assignment_digest"],
            "883dcd2de0057935b01804d59cbcd5a9958772e1188b1243d998df2bc2d2af23",
        )

    def test_seeded_analysis_matches_independent_reference(self) -> None:
        result = run_experiment(self.units)
        control, treatment = result["arms"]["control"], result["arms"]["treatment"]
        self.assertEqual(
            (control["units"], control["conversions"], treatment["units"], treatment["conversions"]),
            (172, 47, 148, 61),
        )

        control_rate, treatment_rate = 47 / 172, 61 / 148
        difference = treatment_rate - control_rate
        unpooled_se = math.sqrt(
            treatment_rate * (1 - treatment_rate) / 148
            + control_rate * (1 - control_rate) / 172
        )
        pooled_rate = (47 + 61) / 320
        pooled_se = math.sqrt(pooled_rate * (1 - pooled_rate) * (1 / 148 + 1 / 172))
        reference_p_value = math.erfc(abs(difference / pooled_se) / math.sqrt(2))

        analysis = result["analysis"]
        self.assertAlmostEqual(analysis["absolute_lift"], difference, places=6)
        self.assertAlmostEqual(
            analysis["confidence_interval_lower"],
            difference - 1.959963984540054 * unpooled_se,
            places=6,
        )
        self.assertAlmostEqual(
            analysis["confidence_interval_upper"],
            difference + 1.959963984540054 * unpooled_se,
            places=6,
        )
        self.assertAlmostEqual(analysis["p_value"], reference_p_value, places=6)
        self.assertTrue(analysis["statistically_significant"])
        self.assertEqual(analysis["decision"], "ADVANCE_TO_LIVE_PILOT")

    def test_impact_is_bounded_to_the_simulated_sample(self) -> None:
        result = run_experiment(self.units)
        impact = result["impact"]
        reference_incremental = (61 / 148 - 47 / 172) * 148
        reference_gross = reference_incremental * 24.0
        reference_cost = 148 * 0.75
        self.assertAlmostEqual(impact["incremental_enrollments_in_sample"], reference_incremental, places=2)
        self.assertAlmostEqual(impact["gross_annualized_value"], reference_gross, places=2)
        self.assertAlmostEqual(impact["total_treatment_cost"], reference_cost, places=2)
        self.assertAlmostEqual(
            impact["roi"], (reference_gross - reference_cost) / reference_cost, places=6
        )
        serialized = json.dumps(result)
        self.assertNotIn("ACC-00001", serialized)
        self.assertIn("no real business lift is claimed", result["data_notice"])

    def test_duplicate_units_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be unique"):
            run_experiment(["ACC-00001", "ACC-00001"])


if __name__ == "__main__":
    unittest.main()
