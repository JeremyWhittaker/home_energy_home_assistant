# Commissioning and acceptance

## Release and deployment state — November 5, 2026

The first installation was commissioned August 30, 2026; Peak Controls followed August 31. Those dated checks establish the original installation, not current runtime health or the later seasonal controller.

The November 4 rebuild deployed controller 0.2.1. The reviewed **0.2.2 update is installed November 5**: exact component hashes matched source, the original energy entries returned loaded, Core reached RUNNING and Honeywell republished all three cooling zones. Saved inverter and A/C response switches were preserved. The inverter controller returned Applied and verified with no error; an independent fresh frame showed 100% charge, no battery discharge and energized mains off peak.

Dashboard/alert configuration has exact readback with 11 dashboard and 103 automation-template checks. All 28 desktop/mobile light/dark cases passed, with 80 screenshots and zero browser errors. The browser profile cleanup then hit a file-removal race; the exact profile was removed after proving no owned browser remained, and bounded cleanup retries were added. The restart checker was also corrected to require Core RUNNING, after its original API/entry-only check returned before Honeywell had finished startup.

- [Home Energy](http://172.16.106.12:8123/home-energy/whole-home)
- [EG4 Solar & Battery](http://172.16.106.12:8123/eg4-energy/live)

The master starts off on a new installation, but the actual inverter master was enabled November 4 after reviewed readback. Re-deployment must preserve existing master/helper values; it is not an instruction to turn them off or reset household thermostat targets.

## Dated evidence and its limits

| Observation | Result | Limit |
| --- | --- | --- |
| August 30–31 original deployment | Loaded entry, seven views, idempotent helper/automation deployment; 28 desktop/mobile light/dark cases passed | Historical build/runtime evidence only; old 6–8 PM window and gross-energy tolerance are superseded |
| September 4 cooling-risk enablement | Existing A/C response master enabled after the prior evening's reserve/forecast alerts | Not proof of every future intervention, mode or thermostat provider response |
| November 4 dashboard/source rebuild | Seven unified views and detailed equipment routes received dated visual checks; local Enphase aggregate restored | Tigo discrepancy and unavailable local EG4 dongle readings remain unresolved |
| November 4 winter settings apply after 17:00 | 49 targets read back, 392 saved weekly fields unchanged and 32 protected fields preserved | Applying after peak start did not test the 17:00 boundary |
| November 4 evening and overnight | Retained peak discharge and off-peak non-discharge observed; overnight SOC 46%→74% | Vendor-reported evidence; no independent metering or savings claim |
| November 5 original 05:00 start watch | **FAIL:** early reported charging followed by missing measurements; 130 fresh records below 140 required | Natural peak-start behavior not proven; preserve this failure |
| November 5 later 05:33–09:19 watch | **READY:** 109 qualified peak-demand observations all showed battery support; 207 peak charger-stop records | This later success does not repair the earlier 05:00 failure or 05:20–05:33 gap |
| November 5 end-of-peak window | Five 09:07–09:11 non-discharge records and two 09:18–09:19 EV permission-release records | Battery charging began 07:43 with solar surplus, so timer-caused 09:00 stop was not isolated; no actual EV gain proven |
| Reviewed 0.2.2 corrections | Installed; full Core startup, original entries, preserved switches, exact configuration and fresh separate clock/frame diagnostics verified | Natural next peak start and thermostat persistence remain field checks |

The reviewed net comparator requires 24 distinct valid hourly intervals per source and uses max(1 kWh, 2% of the larger absolute net). Replaying 324 eligible historical days yields 287 within tolerance and 37 exceptions after correcting six tiny numeric equality cases. Separate utility import/export remain unvalidated. The newest complete SRP day may still be revised.

## Updating an existing installation

1. Record the actual loaded config entry, installed version, exact component files and current helpers/masters. Preserve a private backup and rollback plan.
2. Check ownership. On November 4 the component directory was writable while its parent was protected; supported in-place updates did not require a privileged directory swap. Use the audited privileged installer only when the actual target requires it.
3. Validate source/configuration, apply the reviewed component, restart through supported Core controls when Python changed, and require authenticated health plus the same existing config entry returning loaded. Do not create duplicate entries or edit `.storage` while Core runs.
4. Deploy dashboard/helper/automation changes through the existing owner:

```bash
node deploy.mjs
node deploy.mjs --check
```

5. Compare installed hashes/version and fresh state with the intended release. A successful API response or restart alone is not deployment acceptance.
6. Require a second idempotent check, relevant desktop/mobile light/dark rendering, no missing/error cards, and meaningful template/schema checks. The November 5 copy revision passed its 28-case live rendering gate; later changes need their own checks.

For a new root-owned installation, follow the audited installer and [Operations](OPERATIONS.md#safe-redeployment). Do not require a privileged swap merely because the parent directory is protected when the approved update uses already-owned component files.

## Current monitoring and control contract

- Keep existing entity IDs, dashboard URLs, saved master choices and helper values.
- Show unavailable dependent readings rather than zeros. Local Enphase loss must not suppress independently usable battery/grid alerts.
- Label combined solar as mixed EG4 DC/Enphase AC; Tigo is excluded from additive production.
- Grid and battery signs must agree with their equipment pages. No separate backup/main-panel wattages are invented.
- Reserve is inclusive at 20%. Existing 5 kW / five-minute import protection and conservative HVAC guard are unchanged.
- The reviewed household shortfall message requires valid central and conservative estimates both to reach reserve before peak end.
- Four reviewed failure automations create persistent HA diagnostics only, with bounded incident/window latches. No new push recipients or device-control actions are introduced.
- Peak Controls uses actual valid SRP peaks, including both winter windows, and acts only while home. Modes/manual targets are preserved; still-owned targets restore before comfort scheduling takes over.
- A displayed thermostat target is not a later provider acknowledgment or room-comfort result. The 05:00 target reversion and later independently confirmed recovery stay separate evidence.
- Turning inverter control off stops new changes but retains the programmed inverter settings. See [one-step rollback](OPERATIONS.md#one-step-rollback-and-original-summer-baseline) before recovery work.

## Next natural and hardware checks

| Check | Status / required evidence |
| --- | --- |
| Natural 17:00 peak start | Deferred: aligned HA flow plus fresh vendor origin timestamp, voltage/frequency and charger gates |
| November 7 midnight/weekend | Deferred: verify switched settings, midnight endpoint behavior and daytime AC/PV overlap without unintended discharge |
| November 9 weekday return | Deferred: midnight recipe/readback and following 05:00 start |
| November 26/27 holiday and return | Deferred: preserved-table/readback checks and natural dispatch behavior |
| Summer/season boundaries | Deferred: native weekly preservation and later actual May/October transitions |
| Already-home bedtime and risk intervention/release | Deferred: provider-confirmed targets, ownership/trace evidence and manual-change preservation; do not force hardware merely to create a test |
| Utility agreement | Partial: net-only historical comparison with 37 exceptions; no independent directional calibration |
| Actual EV energy | Blocked by unreliable Orange current measurement and offline Grey; state/permission alone is insufficient |
| Panel split and Tigo discrepancy | Blocked by missing independent panel meters and unresolved source discrepancy |
| Local EG4 dongle | Unavailable in the November 4 observation; no speculative register writes |

Do not use “Run actions” on alert/control automations as a routine commissioning shortcut. It bypasses normal conditions and can send messages or operate equipment. No live notification or hardware test was performed for this source slice; any deliberate test needs its own explicit scope and expected result.

## Additional readback exception — November 5

The independent read matches all 49 dispatch targets plus the 20% reserve and all 392 saved weekly values. Of 463 other numeric fields compared with the original November 4 backup, 462 match; `HOLD_SPEC_LOAD_COMPENSATE` changed from 51 to 54. Its exact meaning, units and cause are undocumented in the inspected sources. The controller does not name it as a command target, which alone does not prove vendor operations cannot affect it. Preserve both readbacks and obtain the exact-model/firmware vendor definition before any change. No calibration write or causal conclusion is justified. The original audit failure is preserved; its expected-count assertion also incorrectly counted 49 where the selected set included reserve as a fiftieth value.
