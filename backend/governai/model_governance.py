"""Research-only model comparison, drift evidence, and approval controls."""

from __future__ import annotations

import math
import sqlite3
import statistics
from typing import Sequence


def linear_forecast(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("At least two observations are required")
    xs = list(range(len(values)))
    x_mean, y_mean = statistics.mean(xs), statistics.mean(values)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    slope = (
        sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denominator
        if denominator
        else 0.0
    )
    return max(0.0, y_mean - slope * x_mean + slope * len(values))


def _error_metrics(predictions: Sequence[float], actuals: Sequence[float]) -> dict[str, float]:
    if len(predictions) != len(actuals) or not predictions:
        raise ValueError("Predictions and actuals must be non-empty and aligned")
    errors = [prediction - actual for prediction, actual in zip(predictions, actuals)]
    return {
        "mae": round(statistics.mean(abs(error) for error in errors), 2),
        "rmse": round(math.sqrt(statistics.mean(error**2 for error in errors)), 2),
    }


def standardized_mean_difference(baseline: Sequence[float], current: Sequence[float]) -> float:
    if not baseline or not current:
        raise ValueError("Both drift windows require observations")
    pooled_deviation = math.sqrt(
        (statistics.pvariance(baseline) + statistics.pvariance(current)) / 2
    )
    if pooled_deviation == 0:
        return 0.0 if statistics.mean(baseline) == statistics.mean(current) else math.inf
    return (statistics.mean(current) - statistics.mean(baseline)) / pooled_deviation


def _drift_level(absolute_smd: float) -> str:
    if absolute_smd >= 0.2:
        return "ALERT"
    if absolute_smd >= 0.1:
        return "WATCH"
    return "STABLE"


def build_model_governance(connection: sqlite3.Connection) -> dict[str, object]:
    monthly = list(
        connection.execute(
            "SELECT month, confirmed_loss FROM mart_monthly_loss_kpis ORDER BY month"
        )
    )
    if len(monthly) < 6:
        raise ValueError("Model governance evidence requires at least six monthly observations")
    months = [str(row[0]) for row in monthly]
    actuals = [float(row[1]) for row in monthly]

    folds = []
    baseline_predictions: list[float] = []
    challenger_predictions: list[float] = []
    fold_actuals: list[float] = []
    for index in range(3, len(actuals)):
        baseline_prediction = actuals[index - 1]
        challenger_prediction = linear_forecast(actuals[:index])
        baseline_predictions.append(baseline_prediction)
        challenger_predictions.append(challenger_prediction)
        fold_actuals.append(actuals[index])
        folds.append(
            {
                "month": months[index],
                "actual": round(actuals[index], 2),
                "baseline_prediction": round(baseline_prediction, 2),
                "challenger_prediction": round(challenger_prediction, 2),
                "training_points": index,
            }
        )

    baseline_metrics = _error_metrics(baseline_predictions, fold_actuals)
    challenger_metrics = _error_metrics(challenger_predictions, fold_actuals)
    research_champion = (
        "ols_trend_challenger"
        if challenger_metrics["mae"] < baseline_metrics["mae"]
        else "last_observation_baseline"
    )
    improvement = (
        (baseline_metrics["mae"] - challenger_metrics["mae"]) / baseline_metrics["mae"]
        if baseline_metrics["mae"]
        else 0.0
    )

    midpoint = len(months) // 2
    baseline_months, current_months = months[:midpoint], months[midpoint:]
    rows = list(
        connection.execute(
            "SELECT month, amount, is_cross_border, is_fraud FROM fct_card_transactions ORDER BY month, transaction_id"
        )
    )
    feature_specs = (
        ("transaction_amount", 1, "USD"),
        ("cross_border_rate", 2, "proportion"),
        ("fraud_rate", 3, "proportion"),
    )
    drift_metrics = []
    for feature, column, unit in feature_specs:
        baseline_values = [float(row[column]) for row in rows if row[0] in baseline_months]
        current_values = [float(row[column]) for row in rows if row[0] in current_months]
        smd = standardized_mean_difference(baseline_values, current_values)
        drift_metrics.append(
            {
                "feature": feature,
                "unit": unit,
                "baseline_mean": round(statistics.mean(baseline_values), 6),
                "current_mean": round(statistics.mean(current_values), 6),
                "standardized_mean_difference": round(smd, 6),
                "absolute_smd": round(abs(smd), 6),
                "status": _drift_level(abs(smd)),
            }
        )
    levels = {metric["status"] for metric in drift_metrics}
    drift_status = "ALERT" if "ALERT" in levels else "WATCH" if "WATCH" in levels else "STABLE"

    return {
        "status": "RESEARCH_ONLY_LOCALLY_VERIFIED",
        "model_card": {
            "model_id": "monthly-loss-forecast-challenger-v1",
            "name": "Monthly loss forecast challenger",
            "owner": "Risk Strategy",
            "task": "One-month-ahead confirmed-loss forecasting",
            "intended_use": "Research comparison and governance workflow demonstration on simulated aggregates.",
            "prohibited_use": "Production loss forecasts, capital decisions, customer actions, or automated approvals.",
            "target": "monthly confirmed_loss",
            "features": ["ordered month index"],
            "training_window": f"{months[0]} through {months[-1]}",
            "data_classification": "simulated aggregate financial data",
        },
        "backtest": {
            "method": "expanding-window one-step-ahead",
            "minimum_training_points": 3,
            "fold_count": len(folds),
            "folds": folds,
            "candidates": [
                {"model_id": "last_observation_baseline", "method": "previous month", **baseline_metrics},
                {"model_id": "ols_trend_challenger", "method": "ordinary least squares trend", **challenger_metrics},
            ],
            "research_champion": research_champion,
            "mae_improvement": round(improvement, 6),
            "decision": "RESEARCH_CHAMPION_NOT_PRODUCTION_APPROVED",
        },
        "drift": {
            "method": "absolute standardized mean difference",
            "watch_threshold": 0.1,
            "alert_threshold": 0.2,
            "baseline_window": f"{baseline_months[0]} to {baseline_months[-1]}",
            "current_window": f"{current_months[0]} to {current_months[-1]}",
            "status": drift_status,
            "metrics": drift_metrics,
        },
        "approval_gates": [
            {"gate": "Data quality contract", "status": "VERIFIED_LOCALLY"},
            {"gate": "Time-based backtest", "status": "VERIFIED_LOCALLY"},
            {"gate": "Model risk review", "status": "NOT_RUN"},
            {"gate": "Business owner approval", "status": "NOT_RUN"},
            {"gate": "Production deployment", "status": "BLOCKED"},
        ],
        "data_notice": (
            "Research-only evidence on six months of simulated aggregate data; no production model performance is claimed."
        ),
        "limitations": [
            "Three backtest folds are insufficient for production model selection.",
            "The target is synthetic and does not represent a bank loss process.",
            "Drift thresholds are demonstration policy values, not validated risk tolerances.",
            "No model-risk, business-owner, fairness, stress, or production approval has occurred.",
        ],
    }
