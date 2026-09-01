# SRP peak-demand strategy

## Existing schedule source

The model reuses the editable, holiday-aware JuiceBox schedule already running in Home Assistant:

- Profile: **E-15 Average Demand**
- May–October, Monday–Friday: **2:00 PM–8:00 PM**
- November–April, Monday–Friday: **5:00 AM–9:00 AM** and **5:00 PM–9:00 PM**
- Configured holidays are off peak.
- Start is inclusive and end is exclusive.
- Invalid configuration fails safe and requires attention.

The dashboard does not duplicate the calendar in hidden hard-coded templates; it reads the established helpers and calculates minutes remaining in the active window.

## Alert policy

### Battery at reserve

Trigger when the EG4 bank reaches the editable reserve, default 20%. The test is inclusive (`<= 20.05`) so the inverter's exact 20% floor is caught. If peak begins while already at reserve, the peak-window transition triggers the same alert.

### Battery shortfall forecast

Trigger after the conservative forecast remains in shortfall for two minutes during both an active, valid SRP peak window and the editable Peak Controls window. The message includes minutes to reserve and peak minutes remaining, then states whether automatic response is enabled or still in dry-run mode.

### Live peak import

Trigger after the whole-property EG4 CT reports import at or above the editable threshold, default 5 kW, continuously for five minutes during both an active, valid SRP peak window and the editable Peak Controls window. This is a live demand-risk signal; the SRP billed-demand sensor is delayed context only.

Each alert writes a peak-window event key to a restored `input_text` helper. State transitions provide prompt delivery, while five-minute reconciliation triggers recover safely after Home Assistant or automation restarts. The persisted key prevents minute-by-minute repeats within the same AM/PM peak window. Alerts use both a persistent notification and the existing family notification script.

The exact reserve-floor alert remains independent of the narrower Peak Controls window because reaching the inverter's 20% floor before peak is still useful warning information.

## Peak Controls

Configure the policy at `/home-energy/peak-controls`. The SRP schedule remains the tariff authority; the editable control window narrows when alerts and A/C response may run. The effective period is therefore the intersection of the two. This prevents a user-entered time from turning an off-peak period into peak.

| Setting | Default | Meaning |
| --- | ---: | --- |
| Automatic A/C response | Off | Master permission for thermostat changes; alerts still run when off |
| Alert/response start | 6:00 PM | Start-inclusive local Arizona time |
| Alert/response end | 8:00 PM | End-exclusive alert/response window and release boundary |
| Forecast SOC guardrail | 25% | Forecast response cannot act above this SOC |
| Cooling setpoint increase | +2°F | Amount added to each selected zone's current target |
| Zone enabled | On for all three | Per-zone opt-in |
| Zone maximum | 80°F | Per-zone comfort ceiling |
| Restore still-owned targets | On | Restore only a target the controller still owns |
| Sustained import threshold | 5 kW | Existing editable EG4 whole-property import threshold |

### Activation rule

The controller evaluates once per minute and can activate only once per local date/window:

```text
master enabled
AND SRP schedule valid
AND SRP peak active
AND inside configured control window
AND an eligible selected zone exists
AND not already handled this window
AND (
  forecast shortfall AND SOC <= guardrail
  OR EG4 import risk has remained active for 5 minutes
)
```

For an eligible zone:

```text
new target = min(original target + increase, zone maximum, thermostat maximum)
```

Only a climate already in `cool` mode with numeric targets is eligible. Peak Controls never starts or stops equipment, changes HVAC mode, changes a fan, or lowers a cooling target.

### Ownership and restoration

Before each service call, the controller stores the original and intended target and marks only that zone as owned. Thermostats are staggered by two seconds.

- A later manual or scheduled change to a different target releases that zone.
- A released zone is never overwritten or restored by Peak Controls.
- Master disable, the final minute before configured-window end, actual SRP peak end, or an invalid schedule releases the controller. The response automation is restart-cancelled by those state changes. Release retains ownership for a ten-second grace period so an already-issued thermostat call or external override can settle, then marks the controller inactive and restores only matching targets. The normal periodic pass starts within the final 60 seconds so restoration completes before an exact-end schedule routine can take authority.
- Restoration runs only when enabled and only if the current target still exactly matches the controller-applied target.
- The event key persists across automation reloads, preventing repeated setpoint increases in the same window.
- An interrupted or failed service is reconciled before the status reports the response as fully active.

### Existing climate routines

Three climate entities are in scope:

- Downstairs: `climate.east_ac_down`
- Primary bedroom: `climate.west_ac_down`
- Upstairs: `climate.upstairs_ac`

Existing automations adjust these systems at 6 PM, 8 PM, and 9 PM. Peak Controls does not disable or edit those routines. Their later target change is treated as authoritative: the affected zone is released and Peak Controls will not restore over it.

Before turning on the master, review:

1. The start/end times for the current SRP season.
2. Which zones may participate.
3. The common increase and each zone's maximum comfort temperature.
4. Whether conditional restoration should remain enabled.
5. The live EG4 import threshold and battery planning inputs on Peak Strategy.

Leave the master off to use the same dashboard and alerts as a dry run without any thermostat service calls.
