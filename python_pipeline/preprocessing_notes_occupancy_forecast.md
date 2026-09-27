# Numeric occupancy forecast preprocessing notes

The occupancy forecast estimates `occupancy_pct = max_load / capacity_total`: the
maximum on-board passenger load for a trip as a share of its assigned vehicle capacity.
It is a numeric regression target, not the `crowding_flag` classification probability.

Inputs are scheduled hour/day type, route, vehicle and route metadata, planned runtime,
headway, assigned capacity, and `prior_route_occupancy_mean`. That history is a rolling
mean of the preceding 28 route-direction trips and therefore excludes the requested
trip. The current trip's `max_load`, boardings, `occupancy_pct`, and `crowding_flag` are
excluded to prevent target leakage.

The model uses the independent Phase 7 pandas/PyArrow pipeline with chronological
training (2025-09-01 to 2026-05-01), validation, and untouched test dates (2026-07-02
to 2026-08-31). MAPE is reported only where observed occupancy exceeds 1%, because a
zero occupancy ratio makes ordinary percentage error undefined.
