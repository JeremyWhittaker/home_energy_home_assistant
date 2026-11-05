# Measurement model

## Quality and timing

- **Measured:** source-device telemetry at the stated boundary; it is not independent calibration.
- **Derived:** arithmetic from source readings. An internal consistency check can reject contradictory data but cannot validate a separate meter by itself.
- **Estimated:** an assumption or mixed measurement basis is involved.
- **Utility reported:** delayed SRP intervals/billing context. Existing entities retain their “Utility settled” classification, but the newest complete day may still be revised.

Missing, stale or unusable required data stays unavailable, never zero. Freshness is evaluated by dependency: Enphase loss prevents combined solar and whole-home load, while independently usable EG4 battery/grid data can still support critical alerts.

Source diagnostics label **HA report age**. Invalid numbers or units have no age in the reviewed source. A recent report can repeat an old vendor frame; independent acceptance must inspect the frame's origin timestamp. The inverter controller separately checks its RTC offset, runtime-frame age and receipt provenance; see [Operations](OPERATIONS.md#clock-and-frame-diagnostics).

## Sign conventions

| Signal | Positive | Negative |
| --- | --- | --- |
| EG4 signed service-grid power | Import from SRP | Export to SRP |
| EG4 raw battery power | Charging | Discharging |
| Dashboard battery net | Discharging | Charging |

Zero service-grid net exchange does not mean the mains is disconnected. Grid-presence flags are screening evidence, not an independent voltage measurement.

## Live equations and boundaries

The August timestamp-aligned audit supported this **internal EG4 identity**:

```text
EG4 vendor Consumption = EG4 AC + signed Grid − Rectifier
```

Enphase joins outside EG4 production measurement but inside the service-line CT boundary:

```text
Whole-home load
  = EG4 vendor Consumption + Enphase AC
  = EG4 AC + Enphase AC + signed Grid − Rectifier
```

The two forms reuse the same inverter measurements. Their agreement is not independent proof of utility agreement or either panel's load. An internal residual outside the larger of 100 W or 3% of the dominant signal makes the dependent whole-home model unavailable.

```text
Combined AC supply = EG4 AC + Enphase AC
Combined solar estimate = EG4 PV DC + Enphase AC
Grid import = max(signed Grid, 0)
Grid export = max(−signed Grid, 0)
Dashboard battery net = −EG4 raw battery power
```

Combined solar mixes EG4 panel-side DC with Enphase AC, so it remains an estimate. EG4 local backup loads consume energy before the main-panel branch; neither branch is independently metered. Local consumption does not excuse a discrepancy between two aligned measurements at the same utility boundary.

All EG4 panels have Tigo monitoring, including the known C4 outage. Tigo is excluded from the combined total to avoid counting EG4 panels twice. The unresolved roughly half-size Tigo/EG4 comparison is DC-panel diagnostic evidence; local AC loads do not explain away that difference. No scaling correction is applied.

## Battery forecasts and protection

```text
energy above reserve = 28 kWh × max(SOC − 20%, 0) / 100
central minutes = 60 × energy above reserve / recent mean discharge kW
conservative minutes = 60 × 95% × energy above reserve
                       / max(recent p80 discharge, 7 kW planning value)
```

The 15-minute sample window needs at least five valid samples spanning eight minutes and meaningful discharge of at least 0.3 kW. Exact 20% SOC returns zero reserve minutes. The nominal capacity and reserve are configured assumptions, not measured usable capacity.

The conservative shortfall binary still governs the separate HVAC risk response. The reviewed household warning and shortfall headline require valid **central and conservative** estimates both to reach reserve before peak ends. A conservative planning-floor-only shortfall does not warn the household. These source corrections await deployment at the November 5 checkpoint; reserve and import protection are preserved.

## SRP reconciliation: net energy only

The current comparison ignores the external statistic's cumulative sum, which can be distorted by refetch/replacement. It uses raw hourly values grouped by Phoenix calendar date:

```text
SRP daily net = sum(24 distinct valid SRP hourly net states)
EG4 daily net = sum(import-counter changes) − sum(export-counter changes)
Residual = EG4 daily net − SRP daily net
Tolerance = max(1 kWh, 2% × max(abs(SRP net), abs(EG4 net)))
```

Each source must supply 24 distinct valid hours; duplicate hours cannot fill a gap. The reviewed numerical comparison allows only 1e-9 kWh of binary arithmetic residue at equality. This does not widen the physical allowance. Gross-flow residual percentages are diagnostic context, not a second tolerance or directional validation.

**Separate SRP import and export have not been validated.** A net match cannot independently prove CT calibration, direction-specific counters or the cause of an exception. The latest complete day may still change as SRP revises its intervals. The August 20-hour/5%-of-gross criteria are historical and superseded.

The November audit compared 324 eligible historical days. Replaying those same inputs with the reviewed numerical equality correction yields 287 within tolerance and 37 exceptions; six nominal 1 kWh boundaries change classification. The exceptions remain open. No meter scaling, calibration, interpolation or statistics rewriting is inferred from that result.

## SRP consumption and generation fields

The imported signed net intervals support this comparison. Separate consumption/generation channels are not verified physical totals for either solar array, the home or independent received/delivered utility registers. Their meaning remains unverified for this wiring; a solar/battery installation's behind-the-meter generation cannot be recovered by renaming them. Native Energy totals and source scopes require their own checks.
