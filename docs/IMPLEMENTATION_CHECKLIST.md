# Whole-home energy implementation checklist

Status values: `implemented`, `blocked`, `deferred`, `not applicable`. Source implementation, deployed configuration and observed behavior are separate evidence. This checkpoint is November 5, 2026: live component 0.2.1, with subsequent reviewed source changes awaiting deployment; 0.2.2 is prepared for installation.

| Requirement | Status | Dated evidence or next check |
| --- | --- | --- |
| Explain EG4, separate Enphase, Tigo, batteries, panels and utility boundary | implemented | README, topology and measurement model; panel branches remain unmetered |
| Combine production without double counting Tigo | implemented | EG4 DC plus Enphase AC is labelled estimated; Tigo remains diagnostic |
| Internal whole-home AC equation | implemented | August aligned audit and model regressions; not independent CT calibration |
| Separate backup/main-panel load readings | blocked | Dedicated panel-boundary meters are absent; no invented split |
| Net-only utility comparison | implemented | 24 distinct valid hourly intervals per source; max 1 kWh / 2% of larger absolute net; newest utility day may revise |
| Numeric tolerance equality | implemented | Six exact binary-boundary regressions; 324-day replay: 287 matches / 37 exceptions; deployment pending |
| Independent utility import/export validation | blocked | Received/delivered channels and directional coverage not established |
| Unified seven-view dashboard and equipment links | implemented | November 5 reviewed copy deployed/read back; 28 desktop/mobile/light/dark cases, 80 screenshots, zero browser errors; representative flow captures inspected |
| Inverter automatic winter schedule | implemented | 0.2.1 deployed/enabled November 4 after 17:00; 49 targets and 392 saved weekly fields verified, protection settings preserved |
| Evening retained dispatch and off-peak transition | implemented | November 4 observer and independent vendor-frame evidence; applying after 17:00 did not prove that start |
| Natural 05:00 start under new schedule | deferred | November 5 original watch FAILED after reported charging and missing measurements; do not overwrite with later recovery |
| Later morning battery support | implemented | 109 qualified demand observations with reported discharge; separate later-morning READY |
| Timer-caused 09:00 discharge stop | deferred | Non-discharge and EV permission release observed; solar charging began 07:43, so timer causality was not isolated |
| Natural 17:00 start | deferred | Next natural boundary needs origin-timed vendor frame, voltage/frequency and aligned flow evidence |
| Weekend/holiday/summer transitions | deferred | Observe November 7 midnight/daytime, November 9 switch-back, November 26/27 holiday transition, and later seasonal changes |
| Controller recovery/preview/retry fixes | implemented | Reviewed RTC/frame diagnostics, fresh verification after Blocked, isolated previews, bounded retries and truthful rollback latches; deployment pending |
| Exact 20% reserve and material-import protection | implemented | Inclusive reserve, existing 5 kW / five-minute import path; unchanged by reviewed corrections |
| Meaningful household forecast warning | implemented | Both central and conservative valid shortfall; 7 kW planning/HVAC guard preserved; deployment pending |
| Bounded failure reporting | implemented | Four persistent-only HA diagnostics deployed/read back; controller dependency update and natural observations pending; no new push recipients or device actions |
| Home-only peak cooling response and target ownership | implemented | Actual SRP windows, occupied-home gate, conditional restoration and comfort-scheduler handoff; real risk intervention remains a field check |
| Thermostat command persistence | deferred | 05:00 displayed targets reverted; 05:40 provider confirmation is separate recovery. Unknown setters and physical comfort remain unresolved |
| Source report-age validity | implemented | Invalid values receive no HA report age; vendor-frame timestamps remain independent; deployment pending |
| Tigo discrepancy/local EG4 dongle | blocked | C4 outage, unresolved Tigo/EG4 difference and unavailable local dongle readings remain hardware/source constraints |
| Actual EV energy gain and Grey behavior | blocked | Orange current measurement is unreliable; Grey remains offline. Policy permission/state is not energy delivery |
| Secrets, backups and existing IDs/routes | implemented | Supported deployment backups, journals, strict validation, unavailable states and read-only UI guards preserved |
| Peer review and source tests | implemented | AGY then Claude completed; material findings tracked with independent checks. Current source passes model/native-template/Node validation |
| Reviewed release/deployed UI acceptance | deferred | Configuration/UI readback and 28-case visual acceptance passed. Component installation/fresh runtime verification pending; 0.2.2 prepared for installation |
