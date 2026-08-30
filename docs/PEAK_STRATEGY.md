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

Trigger after the conservative forecast remains in shortfall for two minutes during an active, valid peak window. The message includes minutes to reserve and peak minutes remaining, then recommends reducing A/C demand.

### Live peak import

Trigger after the whole-property EG4 CT reports import at or above the editable threshold, default 5 kW, continuously for five minutes while peak is active. This is a live demand-risk signal; the SRP billed-demand sensor is delayed context only.

Each alert writes a peak-window event key to a restored `input_text` helper. State transitions provide prompt delivery, while five-minute reconciliation triggers recover safely after Home Assistant or automation restarts. The persisted key prevents minute-by-minute repeats within the same AM/PM peak window. Alerts use both a persistent notification and the existing family notification script.

## A/C policy status

Automatic control is **not commissioned**. Three climate entities exist:

- Downstairs: `climate.east_ac_down`
- Primary bedroom: `climate.west_ac_down`
- Upstairs: `climate.upstairs_ac`

Existing automations already adjust these systems between 5 PM and 8 PM, including two routines at exactly 8 PM. Adding an automatic setpoint action without an ownership policy could fight those routines or restore the wrong temperature.

Before arming control, explicitly decide:

1. Which zones may be adjusted.
2. Whether “reduce A/C” means raising the cooling setpoint; this project assumes it does.
3. Maximum allowed setpoint and maximum step, such as +2 °F capped at 78 °F.
4. Minimum forecast confidence and time-to-reserve trigger.
5. Whether occupants can opt out per zone.
6. Which automation owns restoration after peak, and how manual changes are preserved.
7. What happens if telemetry becomes stale after a setpoint change.

Until then, the dashboard shows current climate/target temperatures and the alert recommends action without calling any climate service.
