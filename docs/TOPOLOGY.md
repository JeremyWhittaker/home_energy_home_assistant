# Physical energy topology

## Plain-language description

There are two independent solar systems on the roof:

- **EG4 array:** string-connected panels feed the EG4 18KPV inverter. Tigo devices monitor individual panels on this array only.
- **Enphase array:** a different set of panels uses 14 Enphase microinverters and an Envoy controller. These panels have no Tigo devices.

The two systems join on the 240 V AC side before the property reaches the SRP solar meter. The EG4 grid CTs are installed at that whole-property boundary, so their signed grid reading includes the result of both arrays, both batteries, and all loads.

Two EG4 batteries provide roughly 28 kWh nominal storage. The batteries support a backup panel containing the A/C units and some other circuits. Other circuits are on the regular panel.

```text
                  EG4 ARRAY
              panels + Tigo CCA
                       │
                       v
                  EG4 18KPV <────> two EG4 batteries (~28 kWh)
                       │                    │
                       │                    └────> backup panel
                       │                              ├─ A/C units
                       │                              └─ other backed-up loads
                       │
                       ├─────────────┐
                       │             │
ENPHASE ARRAY          │             v
panels + microinverters└──────> shared 240 V AC point
        │                            │
        v                            v
      Envoy              EG4 whole-property grid CT
                                     │
                                     v
                                  SRP meter
```

## What each integration contributes

| Integration | Role in the whole-home model |
| --- | --- |
| EG4 Web Monitor | EG4 PV/AC, rectifier, battery, SOC, lifetime counters, and authoritative live signed grid CT |
| Enphase Envoy | Local live AC production and lifetime energy for the separate Enphase array |
| Enphase cloud | Service/gateway and microinverter diagnostics; not the preferred live aggregate |
| Tigo Energy | Panel/module diagnostics for the EG4 array only; never additive solar |
| SRP Energy Monitor | Delayed utility-settled net intervals, demand, and bill context |
| JuiceBox peak helpers | Editable E-15 season/day/time/holiday schedule already used in Home Assistant |

## Known current conditions

- Tigo: 44 configured, 43 reporting; C4 is unavailable.
- Enphase: the local aggregate matches the 14-inverter sum; one “Pool shade” location reports zero/cloud trouble.
- EG4: two batteries, 560 Ah reported total, and a 20% operating reserve.
- SRP: the Home Assistant integration currently needs credential reauthentication. Its unavailable state is surfaced rather than converted to zero.

## Important boundary

EG4 “Consumption Power” and “Output Power” are not independent submeter readings for the backup panel. Historical data shows that Consumption is calculated from the EG4 AC/grid/rectifier balance and Output nearly duplicates it. Therefore:

- whole-property load can be reconstructed after adding Enphase;
- backup-panel load cannot be isolated;
- regular-panel load cannot be isolated;
- a CT/submeter at one panel boundary is the required next hardware improvement.
