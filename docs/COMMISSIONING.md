# Commissioning checklist

## Commissioned live state

Commissioning completed on August 30, 2026. Open the installed dashboard at:

- **Home Energy:** `http://172.16.106.12:8123/home-energy/whole-home`
- **EG4 Solar & Battery:** `http://172.16.106.12:8123/eg4-energy/live`

Home Assistant 2026.8.3 reports the Home Energy config entry as `loaded`. The deployed dashboard round-trips unchanged with 6 views, 109 cards, 47 referenced entities, and 5 templates. All three Home Energy alert automations are enabled.

The latest complete common meter day is **August 29, 2026**:

| Reading | Energy |
| --- | ---: |
| SRP settled net import | 128.4 kWh |
| EG4 CT import | 144.8 kWh |
| EG4 CT export | 17.3 kWh |
| EG4 CT net import | 127.5 kWh |
| EG4 minus SRP residual | -0.9 kWh |
| Displayed tolerance | 8.105 kWh |

All 24 SRP hourly intervals were present, so the reconciliation status is **match**. Model-valid, required-telemetry, SRP-available, and meter-match flags were all on after the final restart.

Final visual QA covered every unified view at 1440×1000 and 390×844 in both light and dark themes: 24 cases, 58 full-page screenshots, and zero actionable browser errors. The only allowed console noise came from the pre-existing Advanced Camera Card resource outside this project. The Home Assistant log contained no `home_energy_monitor` errors.

## 1. Install the integration

Run from the repository root:

```bash
export HA_BASE_URL='http://homeassistant.local:8123'
export HA_TOKEN='your-long-lived-administrator-token'
./scripts/install-integration-privileged.sh
```

Why privilege is required: `/config/custom_components` is owned by root and mode 0755 on this appliance. The regular `jeremy` SSH account can read it but cannot create a new component directory.

The currently installed component directory is owned by `jeremy`, so ordinary read-only checks and direct updates to existing writable files do not need privilege. The installer still uses privilege for its recoverable directory-level swap because that operation writes to the root-owned parent directory.

The installer:

1. Builds a token-free archive in a local temporary file.
2. Copies it to an explicit remote temporary path using legacy SCP transport because this appliance's SSH add-on does not advertise SFTP.
3. Uses `sudo` only for the root-owned Home Assistant component path.
4. Moves any prior component to a timestamped backup under `/config/.home_energy_monitor_deployments`, outside the directory Home Assistant scans for integrations.
5. Validates configuration and requests restart through Home Assistant's authenticated API; the SSH add-on's `ha` CLI cannot access the Supervisor API from this user session.
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
