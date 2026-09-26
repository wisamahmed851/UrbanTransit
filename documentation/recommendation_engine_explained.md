# Recommendation Engine and What-If Simulator

## Overview
This document explains the logic and architecture of the Phase 9 operational recommendation engine and what-if simulator. The goal of this phase is to turn analytical insights from Phase 5 and predictive capabilities from Phase 6/7 into actionable operational directives.

## Recommendation Engine (`engine.py`)

The recommendation engine translates historical metrics into prescriptive actions. It operates using entirely rule-based logic to evaluate conditions against configurable thresholds, ensuring determinism and transparency without relying on generative AI API calls.

### How Recommendations are Generated
1. **Data Ingestion**: Reads Parquet datasets (Phase 5 analytics outputs) directly from HDFS using PyArrow and WebHDFS.
2. **Rule Evaluation**: Applies rule logic defined in `config/thresholds.yaml` to categorize recommendations into priority levels: `Critical`, `High`, `Medium`, and `Low`.
3. **Synthesis**: Matches disparate data sets (e.g., merging `persistent_overcrowding` and `demand_supply_gap` for FREQUENCY constraints) to formulate comprehensive action plans.

### Worked Example: CAPACITY Category
**Condition**: The `demand_supply_gap` table explicitly flags a route's `suggestion` as `larger_vehicle`.
**Action**: "Allocate higher-capacity vehicle or add trips."
**Rule Configuration**: High Priority (default).
**Example output**:
```json
{
  "recommendation_id": "REC-012",
  "subject_id": "R012",
  "category": "CAPACITY",
  "action": "Allocate higher-capacity vehicle or add trips.",
  "evidence": "Route R012 (morning_peak): p90 load is 91.0, suggested vehicle type: Articulated Bus, averaging 35.0 denied boardings per trip over 52 days.",
  "priority": "High",
  "estimated_impact": "(Estimate) Providing the suggested capacity per trip will eliminate the observed denied boardings."
}
```

## What-If Simulator (`whatif_simulator.py`)

The what-if simulator forecasts the effect of potential operational changes. Instead of hardcoded tables, it heavily relies on Phase 6 and Phase 7 predictive models (e.g., XGBoost `crowding_flag` and `delay_severity` classifiers) to score mutated feature vectors representing hypothetical future states.

### How it Works
1. **Scenario Input**: Receives a JSON-like object describing the intervention (e.g., `increase_frequency`).
2. **Base State Retrieval**: Extracts a representative feature vector for the target route and time period from the `trip_features` dataset.
3. **Feature Mutation**: Mutates the input array to reflect the proposed scenario. For example, `increase_frequency` reduces `headway_min` proportionally.
4. **Model Inference**: Passes the synthetic feature vector through the established Phase 6/7 ML pipeline components to yield a new probability risk score.
5. **Output**: Synthesizes the differences between base and future state while appending necessary `warning_flags`.

### Worked Example: `increase_frequency` Scenario
**Scenario**: Route R012, Weekday 08:00-09:00, add 2 trips.
**Mechanism**: Current trips per hour are calculated from `headway_min`. Adding 2 trips yields a new, smaller headway. The mutated `headway_min` is passed through the `crowding_flag` XGBoost pipeline.
**Example output**:
```json
{
  "scenario": {
    "type": "increase_frequency",
    "route_id": "R012",
    "time_period": "08:00-09:00",
    "day_type": "weekday",
    "additional_trips": 2
  },
  "result": {
    "scenario_type": "increase_frequency",
    "route_id": "R012",
    "confidence": "estimate",
    "warning_flags": [],
    "baseline_model_inputs": {"headway_min": 16.0, "prior_route_crowding_rate": 0.06129},
    "historical_route_period_context": {"observed_occupancy_pct": 1.3, "observed_boardings": 133.0},
    "estimated_new_headway_min": 10.4,
    "estimated_waiting_time_reduction_min": 2.8,
    "estimated_crowding_probability": 0.008,
    "estimated_demand_coverage_improvement_passengers": 112
  }
}
```

## Limitations
- **Historical Bias**: The recommendation engine uses past data to infer current and future issues. If demand fundamentally shifts (e.g., new infrastructure opening), historical rules may lag.
- **Uncertainty**: What-If results are strict *estimates* based on model probabilities assuming conditionally independent variables. Confounding unobserved effects (like induced demand from higher frequencies) are inherently excluded.
- **Crowding-model scope:** the saved Phase 7 crowding classifier uses route, vehicle, time, headway, and prior-route crowding features; it does **not** use current `occupancy_pct` or `boardings`. Each regenerated what-if record therefore preserves its exact model inputs and observed historical occupancy context, and its score must not be treated as a replacement for the observed occupancy measure.

## Phase 9 actionability gates

The engine writes `reports/phase9_recommendation_audit.json` on every run. It records each configured condition, source-table denominator, flagged share, and min/mean/max evidence metric. The current production gates are deliberately selective: recurring anomalies require at least 80 occurrences in the 30-day window; capacity requires both at least 35 denied boardings per trip and p90 load of at least 90; frequency requires persistent overload on at least 85% of observed days (95% for Critical); and schedule results are deduplicated to one highest-priority recommendation per route. The generated evidence text includes the relevant route/stop identifier and observation count/window.
