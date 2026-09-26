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
  "recommendation_id": "REC-353",
  "subject_id": "R089",
  "category": "CAPACITY",
  "action": "Allocate higher-capacity vehicle or add trips.",
  "evidence": "Route R089 (morning_peak): p90 load is 98.4, suggested vehicle type: Articulated Bus.",
  "priority": "High",
  "estimated_impact": "(Estimate) Providing 120 capacity per trip will eliminate 18 denied boardings per trip."
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
    "estimated_new_headway_min": 7.5,
    "estimated_waiting_time_reduction_min": 2.5,
    "estimated_crowding_probability": 0.421,
    "estimated_demand_coverage_improvement_passengers": 192
  }
}
```

## Limitations
- **Historical Bias**: The recommendation engine uses past data to infer current and future issues. If demand fundamentally shifts (e.g., new infrastructure opening), historical rules may lag.
- **Uncertainty**: What-If results are strict *estimates* based on model probabilities assuming conditionally independent variables. Confounding unobserved effects (like induced demand from higher frequencies) are inherently excluded.
