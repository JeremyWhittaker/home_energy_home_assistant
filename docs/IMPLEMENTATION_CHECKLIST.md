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
| Create professional unified monitoring page | implemented | Six native responsive views in `src/dashboard.mjs`; live install awaits root-owned component-path step |
| Keep EG4 as its own equipment page | implemented | Live sidebar renamed EG4 Solar & Battery; load labels corrected |
| Verify Enphase, Tigo, SRP, and EG4 pages after unified deployment | deferred | EG4 live visual QA complete except one transient final navigation after HA restarted; full cross-page QA follows privileged integration install |
| Alert at exact 20% reserve | implemented | Inclusive reserve calculation and reserve/peak-start automation |
| Alert on forecast shortfall during peak | implemented | Conservative 15-minute forecast and two-minute persistent transition trigger |
| Alert on material peak grid import | implemented | Editable 5 kW threshold and five-minute persistent transition trigger |
| Reduce A/C demand when battery support may end | blocked | Recommendation implemented; automatic service call blocked pending zone/max/restore ownership because existing 5–8 PM automations overlap |
| Preserve backups, rollback, idempotence, and secrets | implemented | Recoverable privileged installer, mode-0600 backup, transaction rollback, semantic discovery, tests |
| Desktop/mobile light/dark visual QA and HA log inspection | deferred | EG4 representative desktop/mobile/light/dark images inspected clean; unified page requires integration install |
| Documentation, independent verification, Git commit, and GitHub push | deferred | Documentation present; final verifier and shipment follow live commissioning or exact blocker handoff |
