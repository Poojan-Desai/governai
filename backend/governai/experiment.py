"""Deterministic, aggregate-only experimentation evidence for Phase 3A."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ExperimentDefinition:
    experiment_id: str
    name: str
    hypothesis: str
    control_label: str
    treatment_label: str
    treatment_allocation: float
    control_conversion_probability: float
    treatment_conversion_probability: float
    alpha: float
    annual_value_per_incremental_enrollment: float
    treatment_cost_per_unit: float


DEFAULT_EXPERIMENT = ExperimentDefinition(
    experiment_id="card-alert-enrollment-v1",
    name="Card alert enrollment experience",
    hypothesis=(
        "A simplified alert-enrollment experience increases seven-day enrollment "
        "completion without changing eligibility."
    ),
    control_label="Current enrollment flow",
    treatment_label="Simplified enrollment flow",
    treatment_allocation=0.5,
    control_conversion_probability=0.28,
    treatment_conversion_probability=0.42,
    alpha=0.05,
    annual_value_per_incremental_enrollment=24.0,
    treatment_cost_per_unit=0.75,
)


def stable_uniform(experiment_id: str, stream: str, unit_id: str) -> float:
    """Map a unit to a stable [0, 1) value using independent named streams."""
    digest = hashlib.sha256(f"{experiment_id}:{stream}:{unit_id}".encode()).hexdigest()
    return int(digest[:16], 16) / 16**16


def stable_assignment(unit_id: str, definition: ExperimentDefinition = DEFAULT_EXPERIMENT) -> str:
    fraction = stable_uniform(definition.experiment_id, "assignment", unit_id)
    return "treatment" if fraction < definition.treatment_allocation else "control"


def _arm_summary(label: str, outcomes: list[bool]) -> dict[str, object]:
    conversions = sum(outcomes)
    units = len(outcomes)
    return {
        "label": label,
        "units": units,
        "conversions": conversions,
        "rate": round(conversions / units, 6),
    }


def run_experiment(
    unit_ids: Iterable[str], definition: ExperimentDefinition = DEFAULT_EXPERIMENT
) -> dict[str, object]:
    units = sorted(unit_ids)
    if not units:
        raise ValueError("An experiment requires at least one assignment unit")
    if len(units) != len(set(units)):
        raise ValueError("Experiment assignment units must be unique")

    outcomes: dict[str, list[bool]] = {"control": [], "treatment": []}
    assignments: list[str] = []
    for unit_id in units:
        arm = stable_assignment(unit_id, definition)
        probability = (
            definition.treatment_conversion_probability
            if arm == "treatment"
            else definition.control_conversion_probability
        )
        converted = stable_uniform(definition.experiment_id, "outcome", unit_id) < probability
        outcomes[arm].append(converted)
        assignments.append(f"{unit_id}:{arm}")

    if not outcomes["control"] or not outcomes["treatment"]:
        raise ValueError("Experiment requires at least one unit in each arm")

    control = _arm_summary(definition.control_label, outcomes["control"])
    treatment = _arm_summary(definition.treatment_label, outcomes["treatment"])
    control_units, treatment_units = int(control["units"]), int(treatment["units"])
    control_rate = int(control["conversions"]) / control_units
    treatment_rate = int(treatment["conversions"]) / treatment_units
    absolute_lift = treatment_rate - control_rate

    unpooled_se = math.sqrt(
        treatment_rate * (1 - treatment_rate) / treatment_units
        + control_rate * (1 - control_rate) / control_units
    )
    critical_value = 1.959963984540054
    ci_lower = absolute_lift - critical_value * unpooled_se
    ci_upper = absolute_lift + critical_value * unpooled_se

    total_conversions = int(control["conversions"]) + int(treatment["conversions"])
    pooled_rate = total_conversions / len(units)
    pooled_se = math.sqrt(
        pooled_rate * (1 - pooled_rate) * (1 / treatment_units + 1 / control_units)
    )
    z_score = absolute_lift / pooled_se if pooled_se else 0.0
    p_value = math.erfc(abs(z_score) / math.sqrt(2))

    expected_treatment_units = len(units) * definition.treatment_allocation
    assignment_se = math.sqrt(
        len(units) * definition.treatment_allocation * (1 - definition.treatment_allocation)
    )
    assignment_z = (
        (treatment_units - expected_treatment_units) / assignment_se if assignment_se else 0.0
    )
    assignment_p_value = math.erfc(abs(assignment_z) / math.sqrt(2))

    statistically_significant = p_value < definition.alpha and ci_lower > 0
    incremental_enrollments = absolute_lift * treatment_units
    gross_value = incremental_enrollments * definition.annual_value_per_incremental_enrollment
    treatment_cost = treatment_units * definition.treatment_cost_per_unit
    net_value = gross_value - treatment_cost
    roi = net_value / treatment_cost if treatment_cost else 0.0
    decision = (
        "ADVANCE_TO_LIVE_PILOT"
        if statistically_significant and net_value > 0
        else "HOLD_FOR_MORE_EVIDENCE"
    )

    return {
        "experiment_id": definition.experiment_id,
        "name": definition.name,
        "status": "SIMULATED_LOCALLY_VERIFIED",
        "hypothesis": definition.hypothesis,
        "design": {
            "randomization_unit": "account_id",
            "analysis_population": len(units),
            "treatment_allocation": definition.treatment_allocation,
            "assignment_method": "SHA-256 deterministic bucketing",
            "assignment_digest": hashlib.sha256("\n".join(assignments).encode()).hexdigest(),
            "sample_ratio_mismatch_p_value": round(assignment_p_value, 6),
            "sample_ratio_mismatch_detected": assignment_p_value < 0.01,
            "alpha": definition.alpha,
        },
        "metric": {
            "metric_id": "alert_enrollment_completion_7d",
            "name": "Seven-day alert enrollment completion rate",
            "unit": "proportion",
            "direction": "increase",
            "numerator": "Assigned accounts completing alert enrollment within seven days",
            "denominator": "All assigned eligible accounts",
        },
        "simulation_assumptions": {
            "control_conversion_probability": definition.control_conversion_probability,
            "treatment_conversion_probability": definition.treatment_conversion_probability,
            "outcome_method": "Independent SHA-256 outcome stream with predeclared arm probabilities",
        },
        "arms": {"control": control, "treatment": treatment},
        "analysis": {
            "absolute_lift": round(absolute_lift, 6),
            "relative_lift": round(absolute_lift / control_rate, 6) if control_rate else None,
            "confidence_level": 0.95,
            "confidence_interval_lower": round(ci_lower, 6),
            "confidence_interval_upper": round(ci_upper, 6),
            "confidence_interval_method": "unpooled Wald interval",
            "significance_test": "two-sided pooled two-proportion z-test",
            "z_score": round(z_score, 6),
            "p_value": round(p_value, 6),
            "statistically_significant": statistically_significant,
            "decision": decision,
        },
        "impact": {
            "incremental_enrollments_in_sample": round(incremental_enrollments, 2),
            "annual_value_per_incremental_enrollment": definition.annual_value_per_incremental_enrollment,
            "gross_annualized_value": round(gross_value, 2),
            "treatment_cost_per_unit": definition.treatment_cost_per_unit,
            "total_treatment_cost": round(treatment_cost, 2),
            "net_annualized_value": round(net_value, 2),
            "roi": round(roi, 6),
            "currency": "USD",
        },
        "data_notice": (
            "Deterministic simulated outcomes validate experimentation mechanics only; "
            "no customers were exposed and no real business lift is claimed."
        ),
        "limitations": [
            "Outcome probabilities are declared simulation inputs, not estimates from customer behavior.",
            "The confidence interval and p-value describe this seeded demonstration only.",
            "ROI uses portfolio-demo assumptions and must not be used for an investment decision.",
            "A live pilot requires eligibility review, power analysis, guardrails, privacy approval, and monitoring.",
        ],
    }
