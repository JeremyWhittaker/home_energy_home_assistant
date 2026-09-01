# Whole-home energy implementation checklist

Status values: `implemented`, `blocked`, `deferred`, `not applicable`.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Explain EG4, Enphase, Tigo, batteries, panels, and SRP topology plainly | implemented | `README.md`, `docs/TOPOLOGY.md` |
| Verify EG4 source semantics and two-battery capacity/reserve | implemented | Seven-day aligned audit; calculation model/tests; `docs/MEASUREMENT_MODEL.md` |
| Treat Enphase as a separate array | implemented | Local aggregate equals 14-inverter sum; Enphase is added once in whole-home equation |
| Treat Tigo as EG4-only diagnostics and identify the failed module | implemented | 44 configured/43 reporting, known C4 outage; Tigo excluded from combined solar |
| Use SRP net only and explain misleading usage/production channels | implemented | Hourly/daily reconciliation audit and Grid & SRP view |
| Calculate total production and whole-home usage without inventing panel split | implemented | Balance-checked custom integration; backup/regular split explicitly unavailable |
| Create professional unified monitoring page | implemented | Seven native responsive views in `src/dashboard.mjs`, live at `/home-energy/whole-home` |
| Commission unified page on live Home Assistant | implemented | Home Assistant 2026.8.3 reports the config entry `loaded`; the dashboard round-trip contains 7 views, 131 cards, 65 referenced entities, and 7 dashboard templates |
| Keep EG4 as its own equipment page | implemented | Live sidebar renamed EG4 Solar & Battery; load labels corrected |
| Verify Enphase, Tigo, SRP, and EG4 pages after unified deployment | implemented | Existing EG4, Enphase, and Tigo equipment dashboards passed their project QA; SRP is loaded/current, and the unified Diagnostics view retains direct links to all four pages |
| Alert at exact 20% reserve | implemented | Inclusive reserve calculation and reserve/peak-start automation |
| Alert on forecast shortfall during peak | implemented | Conservative 15-minute forecast and two-minute persistent transition trigger |
| Alert on material peak grid import | implemented | Editable 5 kW threshold and five-minute persistent transition trigger |
| Add a configurable Peak Controls dashboard tab | implemented | Live native `/home-energy/peak-controls` view with master, 6–8 PM window, 25% guardrail, +2°F response, per-zone toggles/caps, restoration, live risk, and audit state |
| Limit forecast/import alerts to the configured response window | implemented | Deployed shared start-inclusive/end-exclusive time-window gate for both risk alerts; exact 20% reserve alert remains independent |
| Reduce A/C demand when battery support may end | implemented | Deployed master-disabled one-shot automation raises only selected cooling targets for forecast+SOC or sustained-import risk; never changes HVAC mode |
| Preserve manual and scheduled thermostat authority | implemented | Deployed per-zone original/applied/ownership helpers, override guard, conditional restore, and explicit 6/8/9 PM coexistence contract |
| Deploy and visually verify Peak Controls with the HVAC master off | implemented | Transactional deploy created 24 helpers, verified 22 create-only defaults, updated 5 automations, and round-tripped 80 automation templates; master/controller/owned flags stayed off and thermostat targets remained 70°F, 70°F, and 72°F |
| Restore SRP context in Home Assistant | implemented | The unchanged credentials recovered automatically Aug 30 at 1:46 PM Arizona time; config entry is loaded, no SRP reauth flow exists, and all six entities are available with data through Aug 29 |
| Preserve backups, rollback, idempotence, and secrets | implemented | Recoverable privileged installer with authenticated Core/entry recovery checks, mode-0600 backup, config-entry/site transaction rollback, semantic discovery, tests |
| Desktop/mobile light/dark visual QA and HA log inspection | implemented | All 7 unified views passed 28 desktop/mobile light/dark cases and 72 full-scroll screenshots with 0 Lovelace error cards and 0 browser errors; no relevant Home Energy errors appeared in the HA log |
| Documentation, independent verification, Git commit, and GitHub push | implemented | Independent code review returned GO with no blocker/high/medium issue; Node 19/19, Python 15/15, Ruff, live templates, runtime traces, idempotence, visual QA, and Git push all passed |
