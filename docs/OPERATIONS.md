# Operations and troubleshooting

## Normal operation

The custom integration updates every minute. It keeps a rolling 15-minute battery-discharge window, refreshes Tigo timestamp alignment when a new cloud sample appears, and refreshes the settled SRP/EG4 reconciliation every four hours.

The most useful first checks are:

1. `sensor.home_energy_source_health`
2. `binary_sensor.home_energy_telemetry_healthy`
3. `binary_sensor.home_energy_measurement_model_valid`
4. The **Diagnostics** dashboard view

Every model entity includes `classification`, `calculation_version`, and `measurement_model` attributes. Derived/estimated entities also expose their formula or forecast inputs.

## Safe redeployment

Run the component installer only when Python integration code changed. It preserves the previous component at a timestamped hidden directory under `/config/custom_components`.

Run `node deploy.mjs` for dashboard/helper/automation changes. Before mutation it writes a private backup under `/tmp/home-energy-ha-*/backup.json`; deployment is idempotent and automatically restores site objects changed in the current run if a later verification fails.

Always finish with:

```bash
node deploy.mjs --check
```

## Common states

### Whole-home load unavailable

Open Diagnostics. Whole-home load requires fresh EG4 AC, rectifier, vendor Consumption, grid CT, and local Enphase production. Combined solar separately requires EG4 PV and Enphase. A stale/missing dependent source or an AC-bus residual outside tolerance fails only that calculation closed; fresh battery and grid feeds can still drive their critical peak alerts.

### Battery ETA unavailable

This is expected while charging, standing by, during the first eight minutes after integration startup, or when fewer than five valid discharge samples exist.

### Tigo problem stays on

The current baseline is 43 of 44 reporting with C4 down. Tigo is diagnostic only, so this does not invalidate whole-home production. Investigate the Tigo page when the count drops below 43 or another position fails.

### SRP values unavailable

Repair credentials on the existing SRP config entry. Live power and battery alerts continue using the EG4 CT; only settled reconciliation and billing context are lost.

### SRP and EG4 do not match

Check that the reconciliation date is complete, has at least 20 SRP intervals, and is not older than two days. Small daily differences are expected from interval boundaries and meter timing. Investigate repeated residuals outside the displayed greater-of-1-kWh-or-5% tolerance.

### Alert did not fire at 20%

Verify the reserve binary sensor changed from off to on and the alert automation is enabled. The dedicated automation handles exact 20%; the older generic daily digest checks strictly below 20 and is not part of this strategy.

Each alert also reconciles every five minutes and stores its last AM/PM peak-window key in an `input_text.home_energy_*_alert_key` helper. This recovers conditions that were already active at restart without repeating the same alert throughout the window.

## Secrets and backups

- Keep `HA_TOKEN` in the environment only.
- Do not commit `.env`, dashboard backups, screenshots, runtime databases, or credentials.
- Dashboard backups intentionally include the Home Assistant base URL but never the token.
- Component backups live on the HA appliance; review and remove old timestamped copies manually only after a stable operating period.
