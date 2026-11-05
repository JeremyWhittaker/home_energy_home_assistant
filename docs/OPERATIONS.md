# Operations and troubleshooting

## Normal operation

The custom integration updates every minute. It keeps a rolling 15-minute battery-discharge window, refreshes Tigo timestamp alignment when a new cloud sample appears, and refreshes the settled SRP/EG4 reconciliation every four hours.

The most useful first checks are:

1. `sensor.home_energy_source_health`
2. `binary_sensor.home_energy_telemetry_healthy`
3. `binary_sensor.home_energy_measurement_model_valid`
4. The **Diagnostics** dashboard view

Every model entity includes `classification`, `calculation_version`, and `measurement_model` attributes. Derived/estimated entities also expose their formula or forecast inputs.

Configure demand response on **Home Energy → Peak Controls** (`/home-energy/peak-controls`). Editing helpers there does not require a redeploy. The automatic A/C response master is separate from the alert automations, so the page continues to forecast and alert while thermostat control is off.

## Peak Controls operation

Use this order when commissioning or changing the rule:

1. Leave **Enable automatic A/C response** off.
2. Verify the shared SRP calendar and its calculator freshness. Both winter peaks and the summer peak apply; the old 6–8 PM helpers no longer limit timing.
3. Set the SOC guardrail and common cooling-target increase.
4. Select participating zones and set each zone's maximum comfort temperature.
5. Review live battery ETA, EG4 grid import, thermostat targets, and the read-only controller audit.
6. Turn on the master only when those values are correct.

Turning the master off is the normal emergency stop. If the controller is active, this cancels the response immediately, retains ownership for a ten-second settling period so any already-issued thermostat call or external override can be observed, then performs conditional restoration and clears ownership before reporting inactive. A thermostat is restored only when restoration is on and its current target still equals the value Peak Controls applied. A manual or scheduled change to a different target is preserved. The periodic release normally starts in the final 60 seconds of the actual SRP peak so exact-end routines take authority afterward.

Do not edit the `home_energy_hvac_controller_*`, `home_energy_hvac_*_owned`, previous-target, or applied-target helpers from Developer Tools. They are internal ownership records. Their read-only values are summarized on the dashboard.

## Safe redeployment

Run the component installer only when Python integration code changed. It preserves the previous component under `/config/.home_energy_monitor_deployments`, outside `/config/custom_components` so Home Assistant cannot mistake a backup for another integration. For an upgrade, success requires both authenticated Core health and the existing Home Energy config entry returning to `loaded`; otherwise the installer restores the prior component and verifies recovery.

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

First open **Settings → Devices & services → SRP Energy Monitor** and check the entry state, then inspect the integration log. A temporary unavailable state does not prove the password is wrong: the Aug 28–30 outage recovered with unchanged credentials. The installed client treats an access-denied 403 as retryable; only an explicit 400/401 rejection should start reauthentication.

If Home Assistant has opened an SRP reauthentication flow, update the existing entry there. Otherwise leave the credentials alone and allow the four-hour poll to retry. Do not create a duplicate account entry. Live grid power and battery alerts continue using the EG4 CT while SRP is down; only delayed settlement reconciliation and billing context are unavailable.

### SRP and EG4 do not match

Check that the reconciliation date is complete, has at least 20 SRP intervals, and is not older than two days. Small daily differences are expected from interval boundaries and meter timing. Investigate repeated residuals outside the displayed greater-of-1-kWh-or-5% tolerance.

### Alert did not fire at 20%

Verify the reserve binary sensor changed from off to on and the alert automation is enabled. The dedicated automation handles exact 20%; the older generic daily digest checks strictly below 20 and is not part of this strategy.

Each alert also reconciles every five minutes and stores its last AM/PM peak-window key in an `input_text.home_energy_*_alert_key` helper. This recovers conditions that were already active at restart without repeating the same alert throughout the window.

### Peak Controls did not adjust a thermostat

Check the controller audit on the Peak Controls tab. The expected safe skip reasons are:

- master is off;
- SRP schedule is invalid, off peak, or outside the configured control window;
- battery forecast is not in shortfall or SOC is above the guardrail;
- EG4 import has not remained above threshold for five continuous minutes;
- the current date/window was already handled;
- the zone is disabled, unavailable, not in `cool` mode, missing a numeric target, or already at its cap.

### A thermostat was not restored

This is normally intentional. Peak Controls restores only a zone it still owns. A person or another automation changing the target or HVAC mode releases ownership, so the later 8 PM or 9 PM routine cannot be undone. The audit status identifies an externally changed zone.

If the master is off and the controller audit still says active for more than one minute, keep the master off and inspect the three owned flags plus the response/release automation traces before changing any internal helper.

## Secrets and backups

- Keep `HA_TOKEN` in the environment only.
- Do not commit `.env`, dashboard backups, screenshots, runtime databases, or credentials.
- Dashboard backups intentionally include the Home Assistant base URL but never the token.
- Component backups live under `/config/.home_energy_monitor_deployments` on the HA appliance; review and remove old timestamped copies manually only after a stable operating period.

## Inverter schedule control

The inverter master is separate from the A/C response master. Initial setup
leaves `switch.home_energy_automatic_inverter_schedule` off. A controller tick
evaluates the calendar each minute; unchanged profiles receive uncached
verification every 15 minutes, with five-minute error backoff. No repeated writes
are sent when actual settings already match.

Before commissioning, call `home_energy_monitor.apply_inverter_schedule` with
`dry_run: true` and review the returned desired profile, changed fields and
authority change. The dry run may preserve the numeric baseline in HA's local
Store; it does not change the inverter. Then enable the switch and verify
`sensor.home_energy_inverter_schedule_status`, `sensor.home_energy_srp_period`,
actual readback, and grid/battery power.

Winter daily targets use the preserved screenshot recipe. Ordinary summer
weekdays and weekends restore the unchanged native weekly summer table;
holidays use explicit off-peak behavior. Native weekly data is backed up via
selector read 200/40 and weekly reads 500/112 and 612/112. Preserve the literal 101
charging workaround. Never substitute forced discharge/export or modify
reserve/protection to obtain a desired flow.

A transaction journal records intent before each write and verifies current
parameters without a cloud cache key. Partial changes trigger bounded rollback.
Interrupted apply/restore or failed recovery disables the master and reports
**Recovery required**. `home_energy_monitor.rollback_inverter_schedule` restores
the last actual change only after checking the original inverter identity and
weekly-table integrity. Routine no-change verification retains that undo record.
Turning control off alone leaves the applied schedule active; it is not rollback.

After a component update, preserve an exact private copy of the affected files,
check HA configuration, restart through the supported Core service, and require
the same config entry to return loaded with version 0.2.0 and the new switch and
sensors. Compare file hashes as well as fresh states before claiming deployment.
Do not use a privileged installer when an owned in-place update is sufficient.
