# Physical energy topology

## Plain-language description

There are two independent solar systems on the roof:

- **EG4 array:** string-connected panels feed the EG4 18KPV inverter. Tigo devices monitor individual panels on this array only.
- **Enphase array:** a different set of panels uses 14 Enphase microinverters and an Envoy controller. These panels have no Tigo devices.

The supplied drawing and Jeremy's wiring description place both systems inside the same utility-service boundary. Jeremy reports the EG4 grid current transformers (CTs) on those SRP service lines. Their signed reading should therefore include both arrays, the batteries and all loads. This is the measurement contract; no independent physical CT survey or calibration is claimed.

Two EG4 batteries provide roughly 28 kWh nominal storage. Jeremy reports loads directly on the EG4 and other loads on the main panel. The exact backed-up circuit list, including where each A/C circuit connects, has not been independently verified.

```text
                  EG4 ARRAY
              panels + Tigo CCA
                       │
                       v
                  EG4 18KPV <────> two EG4 batteries (~28 kWh)
                       ├────────────> EG4 local / backup loads (unmetered)
                       │
                       v
ENPHASE ARRAY ──AC──> shared 240 V AC point ──> main-panel loads (unmetered)
panels + microinverters        │
                              v
                     service-line CT boundary
                              │
                              v
                           SRP meter
```

Power can flow in either direction at the inverter and service boundary. Envoy reports Enphase measurements; it is not a series power-conversion stage in this diagram.

## What each integration contributes

| Integration | Role in the whole-home model |
| --- | --- |
| EG4 Web Monitor | EG4 PV/AC, rectifier, battery charge, lifetime counters and signed service-grid CT when reporting fresh usable data |
| Enphase Envoy | Local live AC production and lifetime energy for the separate Enphase array |
| Enphase cloud | Service/gateway and microinverter diagnostics; not the preferred live aggregate |
| Tigo Energy | Panel/module diagnostics for the EG4 array only; never additive solar |
| SRP Energy Monitor | Delayed utility-settled net intervals, demand, and bill context |
| JuiceBox peak helpers | Editable E-15 season/day/time/holiday schedule already used in Home Assistant |

## Observed conditions — November 4–5, 2026

- Tigo: 44 configured, 43 reporting; C4 is unavailable. This is a reporting gap, not a physical panel test. Aligned Tigo DC readings remain roughly half the EG4 input total.
- Enphase: restored local aggregate matches the 14-inverter sum; one “Pool shade” location reports zero/cloud trouble. A 179-hour local-counter gap through November 4 prevents allocating its catch-up reliably to individual days.
- EG4: two batteries, 560 Ah reported total, and a 20% operating reserve.
- SRP: the existing entry is loaded after the November 4 history repair; 52,920 retained hours were checked. Separate delivered/received utility directions remain unvalidated. Missing data is surfaced rather than converted to zero.
- Local EG4 dongle: unavailable since the November 4 observation. Cloud telemetry/control is a separate path; no speculative local-register writes were made.

## Important boundary

EG4 “Consumption Power” and “Output Power” are not independent submeter readings for the backup panel. Historical data shows that Consumption is calculated from the EG4 AC/grid/rectifier balance and Output nearly duplicates it. Therefore:

- whole-property load can be reconstructed after adding Enphase;
- backup-panel load cannot be isolated;
- regular-panel load cannot be isolated;
- a CT/submeter at one panel boundary is the required next hardware improvement.
