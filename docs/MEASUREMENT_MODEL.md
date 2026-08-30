# Measurement model

## Quality labels

- **Measured:** direct device telemetry at a known physical point.
- **Derived:** deterministic arithmetic using measured inputs with a validation equation.
- **Estimated:** useful, but includes an assumption or mixed measurement basis.
- **Utility settled:** delayed revenue-meter or billing data, not live power.

Missing or stale required data remains unavailable. It is never silently replaced with zero.

Freshness is evaluated by dependency, not with one global gate. Enphase loss makes combined solar and whole-home load unavailable, but it does not suppress an independently fresh EG4 grid-import or battery-reserve alert. Likewise, stale battery telemetry does not hide a valid whole-home load or grid reading.

## Sign conventions

| Signal | Positive | Negative |
| --- | --- | --- |
| EG4 signed grid | Import from SRP | Export to SRP |
| EG4 raw battery | Charging | Discharging |
| Dashboard battery net | Discharging | Charging |

## Certified live equations

Seven days of timestamp-aligned history established this EG4 identity:

```text
EG4 Consumption = EG4 AC + signed Grid − Rectifier
```

Because Enphase joins outside the EG4 production measurement but inside the whole-property grid CT:

```text
Whole-home load
  = EG4 Consumption + Enphase AC
  = EG4 AC + Enphase AC + signed Grid − Rectifier
```

The integration calculates both forms. If the EG4 identity residual exceeds the greater of 100 W or 3% of the dominant signal, the whole-home model fails closed.

```text
Combined AC supply = EG4 AC + Enphase AC

Combined solar estimate = EG4 PV DC + Enphase AC

Grid import = max(signed Grid, 0)
Grid export = max(−signed Grid, 0)

Dashboard battery net = −EG4 raw battery power
```

The combined solar headline is intentionally **Estimated**: EG4 exposes array-side DC while the Envoy exposes Enphase AC. Combined AC supply is the like-for-like alternative.

## Battery forecast

```text
energy above reserve
  = 28 kWh × max(SOC − 20%, 0) / 100

central minutes
  = 60 × energy above reserve / trailing-15-minute mean discharge kW

conservative minutes
  = 60 × 95% × energy above reserve
    / max(trailing-15-minute p80 discharge, 7 kW planning discharge)
```

The forecast is valid only with at least five fresh samples spanning at least eight minutes and meaningful discharge of at least 0.3 kW. Exact 20% SOC returns zero minutes instead of falling through the old “less than 20” gap.

## SRP reconciliation

The integration ignores the external statistic's cumulative `sum`, which can be inflated when a source refetches/replaces its latest interval. It groups the raw hourly `state` values by Arizona calendar date:

```text
SRP daily net = sum(raw SRP hourly net states)
EG4 daily net = daily import-counter change − daily export-counter change
Residual = EG4 daily net − SRP daily net
```

A day needs at least 20 SRP hourly intervals. The commissioned match tolerance is the greater of 1 kWh or 5% of EG4 import-plus-export throughput.

In the audited Aug 25–27 sample, 72 matched hourly intervals had median residual 0 kWh, MAE 0.822 kWh, p95 absolute error 1.5 kWh, and correlation 0.9518. Complete daily residuals were approximately −0.5, +0.7, and +1.4 kWh.

## Why SRP “usage” and “production” are not used

With solar, batteries, and loads behind the same revenue meter, SRP derives separate usage/production channels that do not represent the physical source/load totals. A representative audited day had about 100.65 kWh actual solar and 203.75 kWh estimated whole-home load, while SRP labeled only 52.5 kWh production and 84.9 kWh usage. Its signed net still reconciled. The dashboard therefore treats only SRP net as authoritative.
