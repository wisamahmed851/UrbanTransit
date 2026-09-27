# Delay-severity taxonomy

UrbanTransit IQ uses one explicit four-class target for delay prediction and reporting:

| label | mean trip delay |
|---|---:|
| On Time | less than 5 minutes late (including early running) |
| Minor | 5 minutes up to, but not including, 10 |
| Moderate | 10 minutes up to, but not including, 20 |
| Severe | 20 minutes or more |

`Major` is intentionally **not** a valid label. The generated source data and Phase 4
feature table contain only the four labels above; delays of 20 minutes or more are
classified as `Severe`. No pipeline may invent a `Major` class from an old draft or an
assumed five-level severity scale.

The executable source of truth is `config/thresholds.yaml`:
`delay_severity_contract` declares the labels and training cut-points, and
`delay_severity` declares the matching bands. `config.settings.delay_severity_contract()`
validates that the two stay aligned. Phase 4 Spark feature generation, the independent
Phase 7 Python target construction, and the prediction API all read that contract.

Changing a band changes the target definition, so it requires rebuilding Phase 4 features
and retraining every delay-severity model before the new taxonomy may be served.
