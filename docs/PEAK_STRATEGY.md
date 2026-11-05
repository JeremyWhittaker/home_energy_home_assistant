# SRP peak and thermostat policy

## One seasonal calendar

Home Energy reads the existing, holiday-aware JuiceBox SRP schedule. The configured plan is **E-15 Average Demand**. Jeremy reported on November 4, 2026 that he had not changed the account plan; the latest bill has not been independently checked here.

| Season | Weekday peak hours, Arizona time |
| --- | --- |
| May–October | 2 PM–8 PM |
| November–April | 5 AM–9 AM and 5 PM–9 PM |

Configured weekends and observed holidays are off peak. Starts are inclusive and ends are exclusive. An invalid or unavailable schedule blocks peak response. The shared calculator must be enabled and its last evaluation must be between zero and 180 seconds old; stale or future timestamps block activation and release an owned response. `sensor.home_energy_srp_period` and the existing schedule helpers show the effective period; EV charging, EG4 scheduling, and thermostat policy must agree with that period.

The former 6–8 PM Home Energy response window is retired. Its two `input_datetime.home_energy_hvac_window_*` helpers retain their IDs and saved values for compatibility, but no longer gate alerts or thermostat changes and are absent from the controls editor. Both winter windows now receive full coverage.

## EG4 battery schedule

The seasonal controller uses supported EG4 controls and verifies settings by reading them back. `sensor.home_energy_inverter_schedule_status` exposes the requested profile, last verification, and any error. The control master starts disabled; a successful service response alone does not prove that settings changed or that the battery physically discharged.

The intended behavior is battery discharge during the applicable SRP peak windows, with off-peak self-consumption prevented by the commissioned EG4 settings. Calendar exceptions, reserve limits, unavailable telemetry, and failed readback require explicit controller status. The commissioned reserve is 20%; battery management can prevent discharge even while the schedule permits it.

After a settings change, verify fresh battery power and utility-boundary grid power through the next complete peak transition. Positive Home Energy battery power means discharge; negative means charging. Positive grid power means SRP import; negative means export. Keep daily meter comparison separate from schedule readback.

## Alerts

| Alert | Trigger |
| --- | --- |
| Battery at reserve | At or below the configured reserve, or peak begins while already at reserve |
| Battery may not last through peak | Conservative forecast remains short of the active peak end for two minutes |
| Sustained peak import | Fresh whole-service CT import remains above the configured threshold for five minutes |

The last two require an active, valid SRP peak. Reserve alerts also run off peak because an empty battery matters for backup; their message distinguishes active peak, an exempt holiday, and ordinary off peak. The saved local-date AM/PM key prevents repeated alerts within the same period and survives automation reloads. Notifications use Home Assistant and the existing family notification script.

The discharge forecast needs at least five fresh samples spanning eight minutes. It remains unavailable during charging, stale telemetry, or insufficient history. The planning capacity is 28 kWh nominal; energy above reserve and minutes remaining are estimates.

## Occupied-home cooling risk response

The response is an extra reduction in cooling demand when peak risk is observed. The separate comfort scheduler owns normal seasonal targets, bedtime, arrival, and away behavior, including winter heating setbacks.

| Setting | Default |
| --- | --- |
| Automatic cooling response | Disabled until enabled explicitly |
| Timing | Every active SRP peak window |
| Required presence | `group.family_presence` must be `home` |
| Forecast SOC guardrail | 25% |
| Cooling target increase | Up to 2°F |
| Zone participation | All three selected |
| Zone comfort ceiling | 80°F |
| Restore still-owned targets | Enabled |
| Sustained grid-import threshold | 5 kW |

The controller acts once per local AM/PM peak when all of these hold:

```text
response enabled
AND family home
AND SRP schedule valid and peak active
AND more than one peak minute remains
AND an eligible cooling zone exists
AND this AM/PM period has not already responded
AND (
  forecast shortfall AND battery charge <= guardrail
  OR grid-import risk has persisted for five minutes
)
```

The family-home and schedule conditions are checked again immediately before each thermostat call. A zone must already be cooling and have numeric targets. Its new target is the smallest of its original target plus the increase, its configured comfort ceiling, and its thermostat limit. This response does not switch modes, start equipment, or lower a cooling target.

A low SOC guardrail can delay action even when the forecast already predicts a shortfall. Historical evidence from September 3, 2026 showed the forecast warning at about 60% charge but the 25% guardrail allowing only about seven minutes of response before peak ended. The guardrail remains editable; do not interpret it as a prediction of how long the battery will last.

## Ownership and handoff

Before changing a zone, the controller saves its original and intended targets and records ownership. Calls are staggered by two seconds. A person or another automation changing a target releases that zone, so later restoration cannot undo the new setting.

Family departure, disabled response, invalid schedule, actual peak end, or its final minute starts release. A ten-second grace period lets an issued thermostat call settle. Restoration runs only when enabled and the current target still equals the controller's applied target. Zone ownership is then cleared, and only after that does the controller report inactive. The override guard skips this release sequence.

The comfort scheduler waits for that inactive signal before applying arrival, away, or peak-end targets. Its wait must be bounded and must not overwrite a still-owned target if release fails. Existing numeric automation IDs and these thermostat entities remain unchanged:

- Downstairs: `climate.east_ac_down`
- Primary bedroom: `climate.west_ac_down`
- Upstairs: `climate.upstairs_ac`

## Reading the energy diagram

EG4 panels all have Tigo optimizers. Tigo observes the same DC production and is never added to EG4 production. The Enphase microinverter array is separate and reports AC power through the local Envoy. A mixed EG4 DC plus Enphase AC total is labeled estimated.

The diagram shows EG4 backup loads before the shared main-panel connection. Their separate power is unavailable because neither branch has an independent submeter. Whole-home load is derived from inverter AC, Enphase AC, signed grid power, and rectifier demand. EG4's calculated consumption supplies an internal consistency identity, not independent proof of the load estimate or utility-meter calibration.

Grid CTs are on the whole SRP service. Daily comparison requires 24 distinct valid hours from both SRP and the EG4 import/export counters. The default engineering tolerance is the larger of 1 kWh or 2% of absolute net energy. Gross-throughput and net residual percentages are reported separately; large simultaneous import/export must not conceal a net discrepancy.

The November 2–3 difference remains unresolved. Historical analysis localized most of the daily difference to the 10 PM Arizona interval, but did not establish a counter reset or a utility error. The November 3 +8.5 kWh difference is outside the new default tolerance.

Local Envoy is authoritative for Enphase production and cumulative history. Cloud power is optional, explicitly estimated, and disabled by default until whole-array equivalence is verified. It cannot replace lifetime energy counters. Tigo comparisons expire with their cloud sample and expose both timestamps and the allowed three-minute alignment skew.
