# Home Energy for Home Assistant

This project turns Jeremy's EG4, Enphase, Tigo, battery, and SRP data into one honest whole-property energy view.

The central rule is simple: **EG4's grid CT is the live net truth at the utility boundary.** EG4 and Enphase are separate solar arrays. Tigo watches the EG4 panels only, so Tigo must never be added as a third source of solar production. SRP's separate “usage” and “production” totals do not match this behind-the-meter wiring; only SRP net energy is used to check the EG4 grid CT.

## Dashboard

After commissioning, open:

- **Whole Home:** `/home-energy/whole-home`
- Solar Arrays: `/home-energy/solar-arrays`
- Battery & Backup: `/home-energy/battery-backup`
- Grid & SRP: `/home-energy/grid-srp`
- Peak Strategy: `/home-energy/peak-strategy`
- Diagnostics: `/home-energy/diagnostics`

The existing `/eg4-energy/live` page remains a separate equipment page named **EG4 Solar & Battery**. Enphase and Tigo keep their own detailed pages as well.

## The system in one picture

```text
EG4 panels ──> EG4 18KPV ──┐
  └─ Tigo module monitors  │
                           ├── 240 V AC bus ──> EG4 whole-property grid CT ──> SRP meter
Enphase panels ─> Envoy ───┘                         │
                                                    ├─ import from SRP (+)
Two EG4 batteries ─> backup panel                   └─ export to SRP (−)
  └─ A/C units and other backed-up circuits
```

Tigo currently reports **43 of 44** modules; position **C4** is the known long-term outage. The two EG4 batteries provide roughly **28 kWh nominal** storage and normally stop supplementing the home at **20% SOC**.

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

Three live automations notify the existing `script.notify_family` targets and create a persistent Home Assistant notification:

1. Battery reaches the commissioned reserve, including the exact 20% floor. It also alerts if a peak window begins while the battery is already at reserve.
2. A conservative 15-minute discharge forecast predicts reserve before the active SRP peak window ends.
3. Whole-property grid import remains above the editable threshold—5 kW by default—for five minutes during peak.

The forecast uses energy above reserve and the greater of recent p80 discharge or the 7 kW planning load. It fails unavailable when telemetry is stale or the sample window is too short.

Automatic thermostat changes are intentionally **not armed**. The dashboard and forecast alert recommend reducing cooling demand, but three existing 5–8 PM climate routines overlap. Zones, maximum setpoint, restoration behavior, and priority must be commissioned before adding climate service calls.

## Install and deploy

The Home Assistant custom-component directory is root-owned on this appliance. Export an administrator API token, then run the audited privileged installer once from this repository. It stages a recoverable copy, runs Home Assistant's configuration check, waits for authenticated post-restart health, and restores the prior component automatically if validation or health fails:

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

The deployer discovers serial-bearing entities semantically, validates every dashboard entity and template against the live server, writes a mode-`0600` backup under `/tmp/home-energy-ha-*`, applies changes transactionally, verifies round trips, and rolls back its site-configuration changes on failure. Tokens are never written to backups.

## Development checks

```bash
node --test
uv run --python 3.12 --extra test ruff check .
uv run --python 3.12 --extra test pytest -q
```

See [Topology](docs/TOPOLOGY.md), [Measurement model](docs/MEASUREMENT_MODEL.md), [Peak strategy](docs/PEAK_STRATEGY.md), [Commissioning](docs/COMMISSIONING.md), and [Operations](docs/OPERATIONS.md).
