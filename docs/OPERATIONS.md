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

## Dashboard ownership and composed navigation

The HomeEnergy owner generates seven base views. On a composed installation, an ordinary
owner apply still installs that base; afterward use the observability owner's composition
check/stage to restore the combined sections from fresh owner dashboards. Verify the resulting
configuration and desktop/mobile rendering before hiding old sidebar entries. Do not hand-edit
the combined dashboard as another source of truth.

`node deploy.mjs --check` recognizes a declared composition and recomputes its entire expected
configuration, source provenance and metadata through supported read-only queries. It rejects
drift without changing the dashboard. It does not itself recompose, deploy or establish visual
or physical-device acceptance. Uncomposed installations retain the normal seven-view check.

Grid & SRP includes the discovered SRP **Demand audit** as a read-only Daily demand check tile.
Tap it for the completed date, daily/half-hour maxima and winning interval. Missing evidence is
incomplete, and unsupported plans remain unsupported. A reported cycle maximum is separate
from an average of daily maxima. Actual billed-dollar line items are not imported; the bill
projection is a total estimate, not a demand charge.

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

Require 24 distinct valid hourly intervals from each source for the same Phoenix day. Compare net energy only with the larger of 1 kWh or 2% of the larger absolute net reading; gross-flow percentages do not provide a second allowance. The newest complete utility day may still be revised. Investigate persistent exceptions without treating a net match as calibration or separate import/export validation.

### Alert did not fire at 20%

Verify the reserve binary sensor changed from off to on and the alert automation is enabled. The dedicated automation handles exact 20%; the older generic daily digest checks strictly below 20 and is not part of this strategy.

The existing reserve/forecast/import alerts reconcile every five minutes and store their last AM/PM window key. New persistent failure diagnostics have their own timing and incident latches; see [Peak failure diagnostics](#peak-failure-diagnostics). A restart resets their ten-minute continuity timer rather than claiming unobserved coverage.

### Peak Controls did not adjust a thermostat

Check the controller audit on the Peak Controls tab. The expected safe skip reasons are:

- master is off;
- SRP schedule is invalid, off peak, or outside the configured control window;
- battery forecast is not in shortfall or SOC is above the guardrail;
- EG4 import has not remained above threshold for five continuous minutes;
- the current date/window was already handled;
- the zone is disabled, unavailable, not in `cool` mode, missing a numeric target, or already at its cap.

### A thermostat was not restored

This is normally intentional. Peak Controls restores only a zone it still owns. A person or another automation changing the target or HVAC mode releases ownership, so the later actual peak-end/comfort routine cannot be undone. The audit status identifies an externally changed zone.

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
verification every 15 minutes, with five-minute error backoff. A blocked/error
status bypasses the healthy-profile shortcut once backoff permits a fresh read;
matching settings recover without rewriting. No repeated writes are sent when
actual settings already match.

Before commissioning, call `home_energy_monitor.apply_inverter_schedule` with
`dry_run: true` and review the returned desired profile, changed fields and
authority change. Check `preview_ready` and `preview_error`; the returned
`status`/`error` still describe the operating controller. A failed preview does
not change its status, backoff, retry budget, verified diagnostics or recovery
latch. Preview receipt/clock diagnostics remain in the response. The dry run may
preserve the initial numeric baseline in HA's local Store; it does not change
the inverter. Then enable the switch and verify
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
A true interrupted apply/restore or failure after a rollback write disables
the master and reports **Recovery required**. A missing journal, changed weekly
table, identity mismatch or clock refusal before a rollback write reports
**Rollback blocked** without inventing an interrupted transaction; an already
interrupted transaction retains its latch even if this attempt stops in
preflight. `home_energy_monitor.rollback_inverter_schedule` restores
the last actual change only after checking the original inverter identity and
weekly-table integrity. Routine no-change verification retains that undo record.
Turning control off alone leaves the applied schedule active; it is not rollback.

Before a component update, preserve an exact private copy of the affected files,
check HA configuration, restart through the supported Core service, and require
Core to return RUNNING and the same config entry to return loaded with backend version 0.2.3
and its expected switch and sensors. SRP demand-audit support uses SRP 1.2.4. Compare file hashes
as well as fresh states before claiming deployment, then follow the owner/recomposition process
above for dashboard changes.
Do not use a privileged installer when an owned in-place update is sufficient.


### Clock and frame diagnostics

`clock_skew_seconds.HOLD_TIME` is the apparent RTC offset at that response's
receipt, with the unchanged ±120-second limit. It is not the runtime-frame age.
`runtime_frame_age_seconds` measures that frame's age at validation, limited to
0–120 seconds. Future frames are refused even when within two minutes.
`clock_received_at` and `clock_receipt_age_seconds` identify the acquisition
receipt for each timestamp; missing, naive, future or older-than-120-second
receipts block. The private snapshot records a receipt for every global/weekly
range. Extra bulk-read elapsed time is not counted as RTC drift, but cannot make
an expired frame or receipt usable. No clock synchronization or larger limit is
performed. Cloud transport delay still limits conclusions about physical RTC
drift; source validation is not an independent clock calibration.

### Automatic retry stop and explicit resumption

Read-only prerequisite/verification failures keep the five-minute backoff and do
not consume the post-write failure budget. Each apply that attempts writes and
fails increments `post_write_failures`, even after its rollback succeeds. After
three consecutive such failures with successful rollback, the controller saves
`retry_exhausted: true`, turns the master off and reports **Automatic retries
stopped**. It remains stopped after restart. Routine ticks and previews cannot
resume it. A successful guarded verification/apply resets the series.

Review the error and actual retained settings, repair the external cause, then
explicitly turn the existing inverter master on to acknowledge and start a new
guarded series. No new force-clear service exists. This acknowledgment cannot
clear **Recovery required** after a genuine partial/interrupted write: use a
successful verified rollback first. A failed rollback remains latched rather
than consuming three more automatic retries. This source slice does not itself
add notification automations; the retry stop is exposed through the existing
status sensor and switch.

### One-step rollback and original summer baseline

The undo journal represents **one last actual controller transaction**. A
Saturday switch replaces the previous weekday-change journal, so rollback then
returns to the prior weekday recipe, not necessarily the original summer
weekly configuration. No-change verification and previews preserve that journal.
The original complete numeric summer baseline remains a separate private
backup; it is not a second undo step. Ordinary summer control restores its
owned fields and original weekly authority only after the saved seven-day table
still matches. All 392 weekly values must remain intact.

For an operator-directed return to the original weekly configuration outside
summer, keep automatic control off and use the supported EG4 portal controls
under a reviewed maintenance plan. First verify the inverter identity and all
seven native weekly tabs against the preserved baseline. Only if that entire
table is still the verified original may it be selected as authority; verify
readback and then restore any controller-owned inactive daily fields from the
same backup. Do not alter reserve, current limits, calibration, protection,
backup or export modes. Never reconstruct missing settings from memory, write
raw registers, or edit Home Assistant's `.storage` to clear a latch.

If a real interrupted transaction is blocked by changed weekly tables or
identity, preserve the baseline/journal and keep the master off. Repair the
verified external mismatch through supported vendor configuration, then retry
the existing rollback and require fresh identity/table/clock/readback success.
If the correct backup or identity cannot be established, recovery remains
blocked for operator review; forcing a clear would remove the safety guarantee.

The effective winter-weekend/holiday recipe remains 00–12 and 12–00 at 4 kW,
PV priority09–15 at12 kW and peak shaving off. Its single pure-policy definition
is admitted before transport. The 101% stop value is still a device workaround.
Midnight endpoint, weekend, holiday and switch-back behavior still require
natural field observations; passing source tests does not establish them.


## Peak failure diagnostics

Four additional automations create **persistent Home Assistant notifications
only**. They do not send a new phone message, retry device commands or change
charging, thermostat or inverter settings. Existing reserve, household forecast
and 5 kW import family alerts retain their IDs and recipients.

- **Missing peak battery support:** valid recent shared SRP rules and usable EG4
  battery/SOC/grid readings, SOC above 25%, reported house load minus solar above
  1 kW, import above a separate 500 W threshold and battery discharge no greater
  than 300 W must persist together for ten minutes. This catches the reported
  morning failure pattern below the existing 5 kW demand/HVAC threshold. It does
  not establish which schedule, hardware or data source caused it.
- **Unusable peak EG4 readings:** battery power, SOC or service-grid values/units
  or their HA report-age qualification fail for ten minutes during valid peak.
  A missing Enphase-dependent house-load estimate alone does not trigger it.
- **Scheduling fault:** Recovery required and Automatic retries stopped report
  immediately when observed; Blocked must last 30 minutes. A five-minute
  reconciliation catches a fault already active when the automation loads.
- **Profile mismatch:** at 04:30 and 16:30 compare the last verified profile with
  the controller's current season/day-kind attributes. Holidays are not
  recalculated in another calendar. This is not a fresh inverter readback.

The first two and the profile check use separate saved date/AM-or-PM keys,
limiting each diagnostic to one per actual peak/window. Controller faults use
status plus its HA state-change time as an incident key; changing attributes
without changing status does not repeatedly report the same incident. Each
class reuses its persistent notification ID, so later incidents replace that
class's existing notification rather than building an unbounded list.

The ten-minute template trigger requires continuous qualification. Home
Assistant restart or automation reload resets that timer; it does not claim
unobserved continuity across downtime. A new sustained condition can report
later if that window has not already been latched. Recovery faults reconcile
without waiting for a new state transition. These notifications do not prove a
physical action or utility outage; consult the controller diagnostics, retained
settings and independently timed vendor/mains evidence.

### Household forecast versus conservative protection

The central estimate divides available energy by recent mean discharge. The
conservative estimate uses 95% of that energy and the greater of p80 discharge
or the existing 7 kW planning value. The conservative shortfall binary and HVAC
risk guard remain unchanged. A household shortfall message and the headline
shortfall status now require a valid sample window with **both** estimates at
or before peak end. The 86%/2.4 kW morning and 82%/3.4 kW evening observations do
not warn solely because 7 kW is conservative; a true central-plus-conservative
shortfall still warns. Reserve and import protection are unchanged.

### HA report ages and numerical comparison equality

The source-health attribute `source_ages_minutes` retains its ID for existing
consumers. Its `source_age_basis` identifies **HA report age; not vendor-frame
age**. Unavailable, unknown, nonfinite, unsupported-unit and out-of-range SOC
values have no age. Valid zero power still has a report age. A republished frozen
vendor frame can still look recent in HA; commissioning must separately check
its vendor origin timestamp.

Settled net-energy comparison allows 1e-9 kWh of binary-arithmetic residue beyond
its displayed boundary. This corrects six audited nominal 1 kWh equality cases;
a genuine 1.1 kWh difference and even 1.00000001 kWh remain outside a 1 kWh
allowance. The physical greater of 1 kWh or 2%-of-larger-absolute-net tolerance is
unchanged. This correction does not calibrate either meter or prove separate
utility import/export directions.


## Demand review email

This source slice targets the parent's planned HomeEnergy 0.2.3 / SRP 1.2.4 rollout; no version metadata or live deployment was changed by the worker. The four persistent failure diagnostics retain their local-only scope. The pre-existing 5 kW / five-minute import alert additionally requests a Jeremy email through the existing configured account, without adding family recipients.

### Routing and current context

Source health exposes `jeremy_email_available`, computed read-only from the real HA service registry plus the existing email account entity. A notify entity's normal `unknown` state is allowed; a missing account or `unavailable` state is not. The template also rechecks account presence. The capability refresh follows the HomeEnergy coordinator; registration can still change between a check and service invocation, so the action is bounded and delivery is never inferred from capability alone.

The peak-import email includes a timestamped current HA snapshot: reported grid import, signed battery power/SOC, inverter status/profile, Orange/Grey EVSE state and thermostat mode/hvac_action. Unknown or unavailable values remain labelled that way. This is not a reconstructed utility interval or proof of current compressor/EV watts. Existing family/persistent actions remain, and their event latch is saved before the email action to prevent restart/timeout duplication. A missing notifier leaves a fixed local persistent notice; the same peak is not repeatedly emailed after recovery.

No destination address is stored in this repository. Routing uses the existing email account with the parent-verified Jeremy default recipient. Changing that account's configured recipient is an operator action, not an automatic discovery decision. Actual inbox delivery remains a separate check; this worker sent no test or alert.

### Utility daily review and bounds

The deployment discovers one enabled SRP Current demand account entry, then requires Demand audit on the same config entry. Renaming account digits is irrelevant; multiple Current demand account candidates or a missing audit refuse ambiguous deployment. Install the compatible SRP audit first. Existing source/entity IDs are preserved.

The review consumes audit state, `last_checked`, `latest_complete_day`, latest daily maximum, exact bounded winning half-hour interval(s), canonical content hash and caveats. It never creates its own utility client, holiday calendar or demand-cost parser. Account E-15 binding must be explicit in the SRP owner; average-demand=true alone cannot distinguish E-15 from E-16. A configured plan is not independently confirmed account enrollment.

A meaningful email candidate requires:

- audit checked within six hours, with no future timestamp and a nonempty canonical hash;
- the latest completed utility day is yesterday or the prior day, never today/future or an old backfill;
- state mismatch, or state matches with daily maximum at/above the existing editable 5 kW threshold;
- local time at/after 10 AM, no attempt already recorded today, and a different day/status/one-decimal daily-max event key from the prior attempt.

New audit states, 10 AM and an hourly reconciliation at minute 15 trigger evaluation. Only the latest completed day is considered; historical arrays are not looped into a message flood at startup. Canonical source hashes detect revisions, but retrieval-only timestamps and nonmaterial row changes do not themselves trigger another email. A material revision can enter a later day's bounded review; a second attempt on the same local day is suppressed.

An incomplete/unsupported/missing/stale audit creates a bounded local persistent diagnostic with no demand-cost email. Each local status/day diagnostic is latched, and reuses a fixed notification ID. Missing utility intervals are never zero. The message separates utility daily/interval checks, derived cycle means and unverified billed dollars. A total bill projection cannot verify the demand-charge component; absent invoice/rate evidence, dollar claims remain unavailable.

Before requesting a daily email, the automation saves its day and material key. That is **attempt intent**, not delivery receipt; it bounds duplicate sends after timeouts or restart. The email action is continue-on-error so failed mail cannot disrupt controls. A local note says the email was requested and delivery is unconfirmed. If the service fails after intent is stored, no automatic resend occurs that day; inspect its trace/log and the local finding rather than silently resending. If capability is missing before intent, findings stay local and a later hourly check may attempt once capability recovers.

The text offers only general discretionary-load timing guidance, labelled as such. Determining a past appliance's contribution requires interval-aligned usable history; unreliable EV CTs, optimistic thermostat states and missing vendor origins remain limitations. No equipment setting or calibrated meter value is changed by this reporting path.
