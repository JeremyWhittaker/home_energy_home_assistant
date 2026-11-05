# Home Energy for Home Assistant

This project turns Jeremy's EG4, Enphase, Tigo, battery, and SRP data into one combined whole-property energy view.

The central rule is simple: **EG4's grid CT is the selected live net reading at the utility boundary.** EG4 and Enphase are separate solar arrays. Tigo watches the EG4 panels only, so Tigo must never be added as a third source of solar production. SRP's separate consumption/generation fields have not been verified as independent import/export or array-production measurements. Only its signed net energy is used to check the EG4 grid CT.

## Dashboard

The commissioned dashboard is live at **[Home Energy](http://172.16.106.12:8123/home-energy/whole-home)**.

Views:

- **Whole Home:** `/home-energy/whole-home`
- Solar Arrays: `/home-energy/solar-arrays`
- Battery & Backup: `/home-energy/battery-backup`
- Grid & SRP: `/home-energy/grid-srp`
- Peak Strategy: `/home-energy/peak-strategy`
- **Peak Controls:** `/home-energy/peak-controls`
- Diagnostics: `/home-energy/diagnostics`

The existing **[EG4 Solar & Battery](http://172.16.106.12:8123/eg4-energy/live)** page remains a separate equipment page. Enphase and Tigo keep their own detailed pages as well.

The dedicated [EG4 project](https://github.com/JeremyWhittaker/eg4_home_assistant) owns inverter and battery detail. This project combines EG4 with the separate Enphase array and utility data. On November 4 the local dongle readings were unavailable; cloud readings supplied the working EG4 monitoring and seasonal controller.

Initial commissioning took place on August 30–31, 2026. The combined dashboard and seasonal controller were rebuilt and deployed on November 4; **0.2.1 remains the live component at this November 5 checkpoint**. Reviewed dashboard and alert configuration is deployed with exact readback; all 28 desktop/mobile light/dark cases passed, and representative flow captures were inspected. Controller and measurement Python corrections await installation; **0.2.2 is prepared for installation**. See [Commissioning](docs/COMMISSIONING.md) for dated acceptance and remaining checks.

Restart acceptance requires Core to report **RUNNING** as well as the original integration entry being loaded. An available API can precede completed startup; thermostat and shared-policy readiness are additional live checks.

The November 5 05:00 battery start was not proven: reported charging was followed by unavailable readings. A later watch recorded 109 qualified peak-demand observations with battery support. The 09:00 watch confirmed off-peak non-discharge and charger permission release, but solar had already caused reported battery charging before 09:00, so a timer-caused stop was not isolated. These results do not establish savings or actual EV energy gain.

## The system in one picture

```text
EG4 panels + Tigo ──DC──> EG4 inverter <──> batteries
                              ├──> local backup loads (unmetered separately)
                              └──> shared AC connection <── Enphase array
                                           ├──> main-panel loads (unmetered separately)
                                           └──> service-line CTs <──> SRP meter
```

The November 4 Tigo observation was **43 of 44** modules reporting; position **C4** is the known long-term outage. The two EG4 batteries provide roughly **28 kWh nominal** storage and normally stop supplementing the home at **20% SOC**.

## What the headline numbers mean

| Reading | Meaning | Quality |
| --- | --- | --- |
| Combined solar | EG4 PV DC + local Enphase AC | Estimated; mixed DC/AC basis |
| Combined AC supply | EG4 AC + Enphase AC | Derived |
| Whole-home load | EG4 AC + Enphase AC + signed grid − rectifier | Derived and balance-checked |
| Grid net | EG4 whole-property CT; positive import, negative export | Measured |
| Battery net | Negative of EG4 raw battery power; positive is discharge | Derived sign normalization |
| SRP settled net | Sum of raw SRP hourly net intervals | Utility settled and delayed |

The dashboard does **not** claim separate backup-panel and regular-panel loads. No installed sensor measures that boundary independently. A dedicated CT/submeter is required to add that split honestly.

## Alerts

The reviewed alert configuration is deployed. Its controller/measurement dependency changes await the Python component update at this checkpoint; natural failure and boundary observations remain separate acceptance.

Three alert automations notify the existing `script.notify_family` targets and create a persistent Home Assistant notification:

1. Battery reaches the commissioned reserve, including the exact 20% floor. It also alerts if a peak window begins while the battery is already at reserve.
2. During an SRP peak, valid central and conservative 15-minute forecasts both predict reserve before peak ends. The central estimate uses recent average discharge; a planning-floor-only shortfall does not warn the household.
3. During that window, whole-property grid import remains above the editable threshold—5 kW by default—for five minutes during peak.

The conservative forecast uses energy above reserve and the greater of recent p80 discharge or the existing 7 kW planning load. It continues to govern the separate HVAC risk response; the household warning and status require the central forecast to agree. Forecasts fail unavailable when telemetry is stale or the sample window is too short.

Four additional automations create persistent Home Assistant diagnostics without adding push recipients or controlling equipment: ten minutes of missing peak battery support despite reported import above 0.5 kW and a load deficit; ten minutes of unusable EG4 battery/SOC/grid values during peak; immediate recovery-required/retry-stop or 30 minutes Blocked; and a saved-profile mismatch at 04:30 or 16:30. Peak diagnostics are limited to one per window, and controller faults to one per continuous status incident. The separate existing 5 kW import threshold and 7 kW planning helper remain unchanged. See [Operations](docs/OPERATIONS.md#peak-failure-diagnostics) for qualification and restart limits.

The **Peak Controls** tab follows every valid SRP peak, including both winter windows. Its optional battery-risk cooling response acts only while the family is home. Defaults are a 25% battery guardrail, a 2°F increase, all three zones selected and an 80°F ceiling. It can respond once per actual morning/evening period when battery reserve is threatened or grid import stays high for five minutes.

The response preserves HVAC modes and snapshots each target before changing it. Manual changes release ownership. At peak end, departure, disabled control or invalid/stale rules, it conditionally restores still-owned targets before reporting inactive. The separate mode-aware household comfort/away scheduler can then take over without racing restoration; old 6–8 PM helpers remain only for existing references.

## Automatic inverter scheduling

The deployed 0.2.1 controller provides a separate **Automatic EG4 schedule** switch. It starts off, persists its choice and uses the existing loaded EG4 cloud client; it stores no additional login. The shared SRP calculator must be enabled, recent, consistent with the E-15 calendar and configured for America/Phoenix. The reviewed source below separates the previously combined clock diagnostics: the inverter RTC offset must stay within ±120 seconds of its response receipt. Runtime frames and clock-response receipts must be no older than 120 seconds, with future runtime/receipt timestamps rejected. These are separate readback guards and diagnostics; a recent cloud poll does not prove recent inverter telemetry.

| Calendar | Inverter behavior |
|---|---|
| Winter weekday | Peak shaving 05–09 and 17–21 at 0 kW grid limit; grid charge 21–05 and 15–17 at 2 kW; PV priority 09–15 at 12 kW |
| Summer ordinary weekday/weekend | Restore and preserve the complete verified native weekly summer table, including distinct 2/4 kW weekday and 4 kW weekend charging |
| Winter weekend; SRP holiday in either season | Explicit daily off-peak preservation with 4 kW charging,09–15 PV priority and peak shaving off |

The uploaded winter 101% charging-stop value is preserved as a device workaround, not physical battery capacity. Reserve, protection, forced export and backup settings are preserved. A complete numeric backup and undo journal are saved locally before changes. The controller programs and reads back daily fields before switching from native weekly authority, then verifies again without using cached acknowledgements. Failures trigger bounded rollback. Three consecutive failures after writes, each with successful rollback, stop automatic retries and turn the master off; reviewing the cause and explicitly re-enabling begins a new guarded series. A failed or interrupted partial rollback instead retains **Recovery required** until a verified recovery succeeds.

A preview returns `preview_ready` and `preview_error` separately from operating status; it preserves status, retry timing and any recovery latch while allowing the first private baseline capture. A blocked controller requires a fresh read before it reports recovery, even inside the normal 15-minute verification interval. The pure approved non-peak recipe and the applied recipe now share the same two 4 kW AC windows (00–12 and 12–00), 09–15 PV priority and disabled peak shaving; this source agreement is not live firmware acceptance.

The dashboard shows current tariff, profile, last verified time and any error. Turning the master off stops further changes but leaves applied settings in the inverter. [Operations](docs/OPERATIONS.md#inverter-schedule-control) describes dry-run and recovery services. Source tests, deployed configuration and observed power flow are separate acceptance steps.

## Install and deploy

Check actual ownership before installation. The existing component directory on the November 4 appliance is user-writable, while its parent is protected; an owned in-place update needs an exact private backup, configuration check and controlled restart. On a root-owned installation, export an administrator API token, then run the audited privileged installer once from this repository. It stages a recoverable copy, runs Home Assistant's configuration check, waits for authenticated post-restart health, requires any pre-existing Home Energy config entry to return to `loaded`, and restores the prior component automatically if validation or health fails:

```bash
export HA_BASE_URL='http://homeassistant.local:8123'
export HA_TOKEN='your-long-lived-access-token'
./scripts/install-integration-privileged.sh
```

Then deploy the config entry, editable helpers, alert automations, and storage-mode dashboard:

```bash
node deploy.mjs
node deploy.mjs --check
```

The deployer discovers serial-bearing entities semantically, validates every dashboard entity plus every dashboard and automation template against the live server, writes a mode-`0600` backup under `/tmp/home-energy-ha-*`, applies changes transactionally, verifies round trips, and rolls back its site-configuration changes on failure. Tokens are never written to backups.

## Development checks

```bash
node --test
uv run --python 3.12 --extra test ruff check .
uv run --python 3.12 --extra test pytest -q
```

See [Topology](docs/TOPOLOGY.md), [Measurement model](docs/MEASUREMENT_MODEL.md), [Peak strategy](docs/PEAK_STRATEGY.md), [Commissioning](docs/COMMISSIONING.md), and [Operations](docs/OPERATIONS.md).

## Measurement corrections and limits

The utility comparison requires 24 distinct valid hourly intervals from each source. It checks **net energy only**, using the larger of 1 kWh or 2% of the larger absolute net reading. Gross-flow percentages are context, not a second match allowance. Separate SRP import and export remain unvalidated. The newest complete utility day may still be revised; missing or failed comparison data clears the cached result. Agreement does not independently calibrate either meter.

Source ages are labelled **HA report age**, with no age supplied for unusable or incorrectly unit-labelled values. A recent report does not prove a recent vendor frame. Net comparison equality includes only a 1e-9 kWh allowance for binary arithmetic, without changing the 1 kWh/2% physical tolerance.

Tigo-to-EG4 comparisons now expire with their source samples and expose alignment/freshness details. Local Enphase remains preferred; a separately identified cloud power fallback is disabled by default until its whole-array scope is verified, and cumulative energy sources are never spliced. The seasonal controller validates the existing shared SRP helpers and uploaded winter profile. Installation leaves new automatic inverter control off until explicitly enabled and verified.
