# Commissioning checklist

## 1. Install the integration

Run from the repository root:

```bash
export HA_BASE_URL='http://homeassistant.local:8123'
export HA_TOKEN='your-long-lived-administrator-token'
./scripts/install-integration-privileged.sh
```

Why privilege is required: `/config/custom_components` is owned by root and mode 0755 on this appliance. The regular `jeremy` SSH account can read it but cannot create a new component directory.

The installer:

1. Builds a token-free archive in a local temporary file.
2. Copies it to an explicit remote temporary path.
3. Uses `sudo` only for the root-owned Home Assistant component path and Core check/restart.
4. Moves any prior component to a timestamped backup.
5. Runs `ha core check` before restart.
6. Waits up to three minutes for authenticated `/api/config` health after restart and, on an upgrade, requires the pre-existing `home_energy_monitor` config entry to return to `loaded`.
7. Restores the prior directory on validation/entry-health failure, restarts again, verifies both Core and prior-entry recovery, and retains the failed copy for inspection.

## 2. Deploy the Home Assistant objects

```bash
node deploy.mjs
```

Expected objects:

- one `home_energy_monitor` config entry;
- 29 calculated/normalized sensors and 9 binary quality/risk sensors;
- four editable `input_number.home_energy_*` helpers and three persisted alert-latch helpers;
- three `automation.home_energy_*` alert automations;
- one storage-mode `home-energy` dashboard with six views.

The exact entity IDs are discovered and verified after Home Assistant creates them; the deployment does not commit serial-bearing source IDs.

## 3. Validate

```bash
node deploy.mjs --check
```

Then verify in the UI:

- `/home-energy/whole-home` renders without error cards on desktop and mobile;
- combined solar is close to EG4 PV plus local Enphase power;
- whole-home load is close to EG4 vendor-calculated load plus Enphase power;
- grid net direction matches the EG4 equipment page;
- battery positive means discharge and negative means charge;
- Tigo shows 43/44 and names C4 as the known outage;
- SRP is clearly unavailable until credentials are repaired;
- alert automations are enabled;
- no automatic thermostat action exists.

## 4. Reauthenticate SRP

The installed SRP integration is loaded but its six entities have been unavailable since Aug 29 because SRP rejected the stored credentials. Reauthenticate the existing config entry through Home Assistant. Do not create a second account entry. After it recovers, allow at least one complete Arizona calendar day before expecting a reconciliation result.

## 5. Test notifications safely

Use Home Assistant's automation **Run actions** control for each new automation while watching both the persistent notification and family targets. Do not lower the live threshold solely to create a long peak import unless you intend to receive that alert.

## Acceptance criteria

- Model-valid and telemetry-healthy flags are on when sources are fresh.
- Whole-home balance residual is inside its displayed tolerance.
- Missing Enphase or EG4 data makes dependent results unavailable, not zero.
- The 20% condition is inclusive.
- Peak import requires five continuous minutes.
- Dashboard, helpers, and automations round-trip identically on a second deploy.
