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
- SRP shows delayed utility data without affecting live EG4 grid/battery alerts;
- alert automations are enabled;
- no automatic thermostat action exists.

## 4. Confirm SRP health

The Aug 28–30 SRP outage recovered without a credential change. The recorder shows the current-demand entity became unavailable at **Aug 28, 9:04 PM Arizona time** and recovered at **Aug 30, 1:46 PM**. On the Aug 30 audit:

- the existing `srp_energy_monitor` config entry was `loaded`;
- no SRP reauthentication flow existed;
- all six SRP entities were available;
- current demand was 6.3 kW and the feed reported data through Aug 29;
- the live component files exactly matched the repository version.

The restart removed the detailed failure log, so the original HTTP response cannot be proven after the fact. The unchanged credentials and automatic recovery rule out an ongoing bad-password condition and point to a transient SRP/API access failure. The installed SRP client treats an access-denied 403 as retryable and reserves reauthentication for an explicit 400/401 rejection.

Do **not** reauthenticate merely because an SRP entity becomes temporarily unavailable. Reauthenticate the existing entry only when Home Assistant opens an SRP reauthentication flow or the SRP integration log records an explicit 400/401 credential rejection. Never create a second account entry. After any extended outage, allow one complete Arizona calendar day before expecting settled reconciliation.

## 5. Test notifications safely

Use Home Assistant's automation **Run actions** control for each new automation while watching both the persistent notification and family targets. Do not lower the live threshold solely to create a long peak import unless you intend to receive that alert.

## Acceptance criteria

- Model-valid and telemetry-healthy flags are on when sources are fresh.
- Whole-home balance residual is inside its displayed tolerance.
- Missing Enphase or EG4 data makes dependent results unavailable, not zero.
- The 20% condition is inclusive.
- Peak import requires five continuous minutes.
- Dashboard, helpers, and automations round-trip identically on a second deploy.
