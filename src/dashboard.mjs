function noActions() {
  return {
    tap_action: { action: "none" },
    hold_action: { action: "none" },
    double_tap_action: { action: "none" },
    icon_tap_action: { action: "none" },
  };
}

function tile(entity, name, icon, columns = 6) {
  return {
    type: "tile",
    entity,
    name,
    icon,
    vertical: true,
    state_content: ["state", "last_updated"],
    grid_options: { columns, rows: 2 },
    ...noActions(),
  };
}

function badge(entity, name, icon) {
  return { type: "entity", entity, name, icon, ...noActions() };
}

function heading(text, icon, style = "title") {
  return { type: "heading", heading: text, heading_style: style, icon };
}

function row(entity, name, icon) {
  return { entity, name, ...(icon ? { icon } : {}) };
}

function markdown(content, rows) {
  return {
    type: "markdown",
    content,
    grid_options: { columns: "full", ...(rows ? { rows } : {}) },
  };
}

function sectionsView({ title, path, icon, badges = [], sections }) {
  return {
    title,
    path,
    icon,
    type: "sections",
    max_columns: 2,
    dense_section_placement: true,
    badges,
    sections,
  };
}

function wholeHomeNarrative(e) {
  return `{% set bad = ['unknown', 'unavailable', 'none', ''] %}
{% set valid = is_state('${e.measurementModelValid}', 'on') %}
{% set healthy = is_state('${e.telemetryHealthy}', 'on') %}
{% if not healthy or not valid %}
## ⚠️ Whole-home estimate unavailable
The model has failed closed instead of showing a misleading zero. **Source health:** {{ states('${e.sourceHealth}') }}. Open **Diagnostics** for the exact issue.
{% else %}
{% set solar = states('${e.combinedSolarPower}') | float %}
{% set load = states('${e.wholeHomeLoad}') | float %}
{% set grid = states('${e.gridNetPower}') | float %}
{% set battery = states('${e.batteryNetPower}') | float %}
## {% if grid < -50 %}☀️ Solar surplus{% elif grid > 50 %}🏠 Supplying the home{% else %}⚖️ Grid neutral{% endif %}
The two arrays are supplying **{{ (solar / 1000) | round(1) }} kW** and the whole property is using **{{ (load / 1000) | round(1) }} kW**.

{% if grid > 50 %}Importing **{{ (grid / 1000) | round(1) }} kW** from SRP.{% elif grid < -50 %}Exporting **{{ ((grid | abs) / 1000) | round(1) }} kW** to SRP.{% else %}Grid exchange is effectively neutral.{% endif %} {% if battery > 50 %}The battery is discharging **{{ (battery / 1000) | round(1) }} kW**.{% elif battery < -50 %}The battery is charging **{{ ((battery | abs) / 1000) | round(1) }} kW**.{% else %}The battery is standing by.{% endif %}
{% endif %}`;
}

function solarNarrative(e) {
  return `## Two independent solar arrays

**EG4** is the inverter/string array with Tigo optimizers on its panels. **Enphase** is a separate 14-microinverter array. Their AC outputs meet before the SRP meter.

The headline combined value is labeled **Estimated** because EG4 reports array-side DC while the Envoy reports Enphase AC. Tigo observes only part of the EG4 array and is never added to production.

[Open EG4 equipment](/eg4-energy/live) · [Open Enphase](/enphase-2103/overview) · [Open Tigo modules](/tigo-energy/overview)`;
}

function batteryForecast(e) {
  return `{% set valid = state_attr('${e.batteryMinutesToReserve}', 'forecast_valid') %}
{% set at_reserve = is_state('${e.batteryAtReserve}', 'on') %}
{% if at_reserve %}
## 🪫 Battery is at its commissioned reserve
State of charge is **{{ states('${e.batterySoc}') }}%**. The EG4 normally stops supplementing the home at this 20% floor.
{% elif valid %}
## 🔋 Conservative reserve forecast
About **{{ states('${e.batteryAvailableEnergy}') }} kWh** remains above reserve. At the recent discharge pattern, the conservative forecast is **{{ states('${e.batteryMinutesToReserve}') }} minutes**, around **{{ as_timestamp(states('${e.batteryReserveEta}')) | timestamp_custom('%-I:%M %p') }}**.
{% else %}
## ⏳ Building a reliable forecast
The forecast needs at least five fresh discharge samples spanning eight minutes. It stays unavailable while the battery is charging or telemetry is stale.
{% endif %}`;
}

function peakNarrative(e) {
  return `{% set peak = is_state('${e.peakWindow}', 'on') %}
{% set schedule_ok = is_state('${e.peakScheduleValid}', 'on') %}
{% if not schedule_ok %}
## ⚠️ Peak schedule needs attention
The peak model fails safe when the editable SRP schedule is invalid.
{% elif not peak %}
## ✅ Off peak
Profile: **{{ states('${e.peakProfile}') }}**. Battery and grid are monitored continuously; demand alerts arm only during the configured peak window.
{% elif is_state('${e.livePeakImportRisk}', 'on') %}
## 🚨 On peak · material grid import
Live import is **{{ (states('${e.gridImportPower}') | float / 1000) | round(1) }} kW**, above the **{{ states('${e.peakImportThreshold}') }} kW** alert threshold. Sustained import can raise billed demand.
{% elif is_state('${e.peakForecastShortfall}', 'on') %}
## ⚠️ On peak · battery shortfall forecast
Battery reserve is forecast in **{{ states('${e.batteryMinutesToReserve}') }} minutes**, with **{{ states('${e.peakMinutesRemaining}') }} minutes** left in the peak window.
{% else %}
## 🛡️ {{ states('${e.peakStrategyStatus}') }}
The battery forecast and EG4 whole-property grid CT are inside their current alert bounds.
{% endif %}`;
}

function climateRecommendation(e) {
  return `{% set shortfall = is_state('${e.peakForecastShortfall}', 'on') %}
{% set peak = is_state('${e.peakWindow}', 'on') %}
## A/C demand strategy
{% if shortfall and peak %}**Action recommended:** reduce cooling demand now—typically by raising cooling setpoints within your comfort limit—so battery support lasts through the peak window.{% else %}No battery-driven A/C adjustment is currently recommended.{% endif %}

Peak Controls is **{{ 'enabled' if is_state('${e.hvacResponseEnabled}', 'on') else 'disabled · dry run only' }}**. Configure its 6–8 PM window, 25% SOC guardrail, +2°F response, zone caps, and safe restoration on the **Peak Controls** tab.

- **Downstairs:** {{ states('${e.downstairsClimate}') }} · {{ state_attr('${e.downstairsClimate}', 'current_temperature') }}° → {{ state_attr('${e.downstairsClimate}', 'temperature') }}°
- **Primary bedroom:** {{ states('${e.primaryClimate}') }} · {{ state_attr('${e.primaryClimate}', 'current_temperature') }}° → {{ state_attr('${e.primaryClimate}', 'temperature') }}°
- **Upstairs:** {{ states('${e.upstairsClimate}') }} · {{ state_attr('${e.upstairsClimate}', 'current_temperature') }}° → {{ state_attr('${e.upstairsClimate}', 'temperature') }}°`;
}

function peakControlsNarrative(e) {
  return `## {{ '🟠 Controller active' if is_state('${e.hvacControllerActive}', 'on') else '⚪ Controller standing by' }}

- **Master:** {{ 'enabled' if is_state('${e.hvacResponseEnabled}', 'on') else 'disabled — alerts remain a dry run' }}
- **Response window:** {{ states('${e.hvacWindowStart}')[0:5] }}–{{ states('${e.hvacWindowEnd}')[0:5] }}
- **Forecast guardrail:** {{ states('${e.hvacSocGuardrail}') }}% SOC · **setpoint increase:** {{ states('${e.hvacSetpointIncrease}') }}°F

{{ states('${e.hvacControllerStatus}') if states('${e.hvacControllerStatus}') not in ['unknown', 'unavailable', ''] else 'No controller action has been recorded yet.' }}

The rule activates once per window when **(forecast shortfall AND SOC ≤ guardrail) OR sustained EG4 grid import**. SRP must report a valid active peak window. It only raises selected thermostats already in cooling mode; it never changes mode or turns equipment off.`;
}

function peakControlsSafety(e) {
  return `## Ownership and restoration

For each selected zone, Peak Controls snapshots the original target and applies:

**new target = min(original + increase, zone cap, thermostat maximum)**

- A manual or scheduled change to a different target immediately releases that zone.
- Released zones are never restored or overwritten.
- Just before the configured end time—or at actual peak end, invalid schedule, or master disable—restoration runs only for a still-owned zone whose target exactly matches the value Peak Controls applied.
- The controller activates at most once per local date/window, including after an automation reload.
- Existing 6 PM, 8 PM, and 9 PM routines remain authoritative.

The master is deployed **off**. Configure the rules here, review the live values, then enable it when ready.`;
}

function peakControlsAudit(e) {
  return `## Controller audit

- **Last status:** {{ states('${e.hvacControllerStatus}') if states('${e.hvacControllerStatus}') not in ['unknown', 'unavailable', ''] else 'No action recorded' }}
- **Last handled window:** {{ states('${e.hvacControllerEventKey}') if states('${e.hvacControllerEventKey}') not in ['unknown', 'unavailable', ''] else 'None' }}
- **SRP schedule:** {{ 'valid' if is_state('${e.peakScheduleValid}', 'on') else 'invalid or unavailable' }} · {{ 'peak active' if is_state('${e.peakWindow}', 'on') else 'off peak' }}
- **Owned targets:** downstairs {{ states('${e.hvacEastOwned}') }}, primary bedroom {{ states('${e.hvacWestOwned}') }}, upstairs {{ states('${e.hvacUpstairsOwned}') }}

These are internal safety latches and are intentionally read-only on this page.`;
}

function diagnosticsNarrative(e) {
  return `{% set issues = state_attr('${e.sourceHealth}', 'issues') or [] %}
## {{ '✅ Measurement model valid' if is_state('${e.measurementModelValid}', 'on') else '⚠️ Measurement model invalid' }}
- **Source health:** {{ states('${e.sourceHealth}') }}
- **Calculation:** EG4 AC + Enphase AC + signed grid − EG4 rectifier
**Cross-check residual:** {{ state_attr('${e.measurementModelValid}', 'balance_residual_w') }} W (allowed {{ state_attr('${e.measurementModelValid}', 'balance_tolerance_w') }} W)

{% if issues %}### Current issues
{% for issue in issues %}- {{ issue }}
{% endfor %}{% else %}No current calculation-source issues.{% endif %}`;
}

export function buildDashboard(discovery) {
  const e = discovery.entities;
  return {
    views: [
      sectionsView({
        title: "Whole Home",
        path: "whole-home",
        icon: "mdi:home-lightning-bolt",
        badges: [
          badge(e.combinedSolarPower, "Solar", "mdi:solar-power"),
          badge(e.wholeHomeLoad, "Whole home", "mdi:home-lightning-bolt"),
          badge(e.gridNetPower, "Grid net", "mdi:transmission-tower"),
          badge(e.batterySoc, "Battery", "mdi:home-battery"),
          badge(e.peakStrategyStatus, "Peak", "mdi:shield-home-outline"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Live whole-property balance", "mdi:chart-sankey-variant"),
              markdown(wholeHomeNarrative(e)),
              heading("Current power", "mdi:flash", "subtitle"),
              tile(e.combinedSolarPower, "Combined solar · estimated", "mdi:solar-power"),
              tile(e.wholeHomeLoad, "Whole-home load · derived", "mdi:home-lightning-bolt"),
              tile(e.gridImportPower, "Grid import · measured CT", "mdi:transmission-tower-import"),
              tile(e.gridExportPower, "Grid export · measured CT", "mdi:transmission-tower-export"),
              tile(e.batteryNetPower, "Battery + discharge / − charge", "mdi:battery-sync"),
              tile(e.batterySoc, "Battery state of charge", "mdi:battery-high"),
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Last 24 hours", "mdi:chart-areaspline"),
              {
                type: "history-graph",
                title: "Whole-property power",
                hours_to_show: 24,
                entities: [
                  row(e.combinedSolarPower, "Combined solar · estimated"),
                  row(e.wholeHomeLoad, "Whole-home load · derived"),
                  row(e.gridNetPower, "Grid net · + import / − export"),
                  row(e.batteryNetPower, "Battery · + discharge / − charge"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              heading("What is—and is not—known", "mdi:information-outline", "subtitle"),
              markdown(`- **Measured:** EG4 whole-property grid CT, battery SOC, source-device telemetry.
- **Derived:** whole-home load and AC balance.
- **Estimated:** combined solar mixes EG4 DC and Enphase AC.
- **Utility settled:** delayed SRP billing data.

The backup-panel and regular-panel loads **cannot be separated** with the installed sensors. A dedicated panel submeter is required; this page never invents that split.`),
            ],
          },
        ],
      }),
      sectionsView({
        title: "Solar Arrays",
        path: "solar-arrays",
        icon: "mdi:solar-panel-large",
        badges: [
          badge(e.eg4PvPower, "EG4 array", "mdi:solar-panel"),
          badge(e.enphasePower, "Enphase array", "mdi:solar-panel-large"),
          badge(e.tigoModuleProblem, "Tigo modules", "mdi:view-grid-outline"),
          badge(e.enphaseActiveMicroinverters, "Enphase microinverters", "mdi:counter"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Array production", "mdi:white-balance-sunny"),
              markdown(solarNarrative(e)),
              {
                type: "distribution",
                title: "Current array contribution · mixed DC/AC",
                entities: [
                  { entity: e.eg4PvPower, name: "EG4 array · DC", color: "#f9a825" },
                  { entity: e.enphasePower, name: "Enphase array · AC", color: "#1e88e5" },
                ],
                grid_options: { columns: "full" },
              },
              tile(e.eg4PvPower, "EG4 PV · measured DC", "mdi:solar-panel"),
              tile(e.enphasePower, "Enphase · measured AC", "mdi:solar-panel-large"),
              tile(e.combinedSolarPower, "Combined · estimated", "mdi:solar-power", 12),
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Array diagnostics", "mdi:stethoscope"),
              {
                type: "entities",
                title: "Health and coverage",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.tigoModuleProblem, "Tigo module problem · C4 known down"),
                  row(e.tigoArrayPower, "Tigo diagnostic power · not additive"),
                  row(e.tigoAlignedEg4Power, "EG4 power aligned to Tigo sample"),
                  row(e.tigoRatio, "Tigo / EG4 aligned coverage"),
                  row(e.enphaseSystemProblem, "Enphase system problem"),
                  row(e.enphaseActiveMicroinverters, "Active Enphase microinverters"),
                ],
                grid_options: { columns: "full", rows: 6 },
              },
              {
                type: "history-graph",
                title: "Array production · 48 hours",
                hours_to_show: 48,
                entities: [
                  row(e.eg4PvPower, "EG4 array · DC"),
                  row(e.enphasePower, "Enphase array · AC"),
                  row(e.tigoArrayPower, "Tigo diagnostic subset"),
                ],
                grid_options: { columns: "full", rows: 6 },
              },
            ],
          },
        ],
      }),
      sectionsView({
        title: "Battery & Backup",
        path: "battery-backup",
        icon: "mdi:home-battery",
        badges: [
          badge(e.batterySoc, "Battery", "mdi:battery-high"),
          badge(e.batteryNetPower, "Battery power", "mdi:battery-sync"),
          badge(e.batteryMinutesToReserve, "To reserve", "mdi:battery-clock-outline"),
          badge(e.batteryAtReserve, "Reserve", "mdi:battery-alert-variant-outline"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Battery bank", "mdi:home-battery-outline"),
              {
                type: "gauge",
                entity: e.batterySoc,
                name: "State of charge",
                min: 0,
                max: 100,
                needle: true,
                severity: { red: 0, yellow: 20, green: 50 },
                grid_options: { columns: "full", rows: 3 },
              },
              markdown(batteryForecast(e)),
              tile(e.batteryNetPower, "Battery + discharge / − charge", "mdi:battery-sync"),
              tile(e.batteryAvailableEnergy, "Energy above reserve · estimated", "mdi:battery-high"),
              tile(e.batteryDischargeAverage, "Discharge average · 15m", "mdi:chart-line"),
              tile(e.batteryDischargeP80, "Discharge p80 · 15m", "mdi:chart-bell-curve-cumulative"),
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Battery behavior", "mdi:chart-timeline-variant"),
              {
                type: "history-graph",
                title: "Battery and whole-home demand · 24 hours",
                hours_to_show: 24,
                entities: [
                  row(e.batterySoc, "Battery SOC"),
                  row(e.batteryNetPower, "Battery · + discharge / − charge"),
                  row(e.wholeHomeLoad, "Whole-home load"),
                  row(e.gridNetPower, "Grid net"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              markdown(`## Backup-panel limitation
The two EG4 batteries provide roughly **28 kWh nominal** and feed the backup panel, including the A/C equipment and other circuits. EG4's “Consumption Power” is an AC-bus balance—not an independent backup-panel CT—so this dashboard cannot truthfully split backup-panel load from regular-panel load.`),
            ],
          },
        ],
      }),
      sectionsView({
        title: "Grid & SRP",
        path: "grid-srp",
        icon: "mdi:transmission-tower",
        badges: [
          badge(e.gridNetPower, "Live grid net", "mdi:transmission-tower"),
          badge(e.gridReconciliationMatches, "Meter match", "mdi:scale-balance"),
          badge(e.srpIntegrationAvailable, "SRP feed", "mdi:cloud-check-outline"),
          badge(e.srpBilledCyclePeak, "Cycle peak", "mdi:chart-timeline-variant"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Live utility boundary", "mdi:meter-electric-outline"),
              markdown(`## The grid CT is the live source of truth
EG4's 240 V grid CT sits at the whole-property utility boundary, after EG4 and Enphase combine. Positive is import; negative is export. This is the only trustworthy live net measurement for the complete property.`),
              tile(e.gridNetPower, "Grid net · + import / − export", "mdi:transmission-tower", 12),
              tile(e.gridImportPower, "Grid import", "mdi:transmission-tower-import"),
              tile(e.gridExportPower, "Grid export", "mdi:transmission-tower-export"),
              {
                type: "history-graph",
                title: "Grid exchange · 48 hours",
                hours_to_show: 48,
                entities: [
                  row(e.gridNetPower, "Grid net · + import / − export"),
                  row(e.gridImportPower, "Import"),
                  row(e.gridExportPower, "Export"),
                ],
                grid_options: { columns: "full", rows: 6 },
              },
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Revenue-meter reconciliation", "mdi:scale-balance"),
              {
                type: "entities",
                title: "Latest common settled day",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.gridReconciliationDate, "Settlement date"),
                  row(e.srpSettledNetEnergy, "SRP revenue-meter net"),
                  row(e.eg4SameDayNetEnergy, "EG4 CT net"),
                  row(e.gridReconciliationResidual, "EG4 minus SRP residual"),
                  row(e.gridReconciliationMatches, "Within commissioned tolerance"),
                ],
                grid_options: { columns: "full", rows: 5 },
              },
              heading("SRP billing context", "mdi:finance", "subtitle"),
              tile(e.srpCurrentDemand, "Current-cycle demand · delayed", "mdi:gauge"),
              tile(e.srpBilledCyclePeak, "Billed cycle peak · delayed", "mdi:chart-line"),
              tile(e.srpBillProjection, "Bill projection · delayed", "mdi:cash-clock", 12),
              markdown(`SRP's separate **production** and **usage** channels do not describe this wiring correctly because the arrays, batteries, and backup-panel loads interact behind the revenue meter. Only SRP's signed **net** intervals are used for verification. [Open SRP detail](/srp-energy)`),
            ],
          },
        ],
      }),
      sectionsView({
        title: "Peak Strategy",
        path: "peak-strategy",
        icon: "mdi:shield-home-outline",
        badges: [
          badge(e.peakWindow, "Peak window", "mdi:clock-alert-outline"),
          badge(e.peakMinutesRemaining, "Peak remaining", "mdi:timer-sand"),
          badge(e.peakForecastShortfall, "Battery forecast", "mdi:battery-clock-outline"),
          badge(e.livePeakImportRisk, "Import risk", "mdi:transmission-tower-alert"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Live peak posture", "mdi:shield-home"),
              markdown(peakNarrative(e)),
              tile(e.peakStrategyStatus, "Peak strategy", "mdi:shield-home-outline", 12),
              tile(e.peakMinutesRemaining, "Minutes left in peak window", "mdi:timer-sand"),
              tile(e.batteryMinutesToReserve, "Conservative minutes to reserve", "mdi:battery-clock-outline"),
              tile(e.gridImportPower, "Live grid import", "mdi:transmission-tower-import"),
              tile(e.srpBilledCyclePeak, "SRP billed peak · delayed", "mdi:chart-timeline-variant"),
              {
                type: "history-graph",
                title: "Demand-defense signals · 12 hours",
                hours_to_show: 12,
                entities: [
                  row(e.wholeHomeLoad, "Whole-home load"),
                  row(e.gridImportPower, "Grid import"),
                  row(e.batteryNetPower, "Battery discharge"),
                  row(e.batterySoc, "Battery SOC"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Cooling-load response", "mdi:thermostat"),
              markdown(climateRecommendation(e)),
              heading("Commissioned thresholds", "mdi:tune-variant", "subtitle"),
              {
                type: "entities",
                title: "Editable helpers",
                show_header_toggle: false,
                entities: [
                  row(e.batteryCapacity, "Nominal battery capacity"),
                  row(e.batteryReserve, "Battery reserve"),
                  row(e.planningDischarge, "Conservative planning discharge"),
                  row(e.peakImportThreshold, "Live peak import threshold"),
                  row(e.peakProfile, "SRP schedule profile"),
                  row(e.peakScheduleValid, "Peak schedule valid"),
                ],
                grid_options: { columns: "full", rows: 6 },
              },
              markdown(`Alerts go to the existing **Family notification** script and Home Assistant persistent notifications. They fire when the battery reaches 20%, when the conservative forecast reaches reserve before peak ends, and after material peak import persists for five minutes.`),
            ],
          },
        ],
      }),
      sectionsView({
        title: "Peak Controls",
        path: "peak-controls",
        icon: "mdi:thermostat-auto",
        badges: [
          badge(e.hvacResponseEnabled, "HVAC master", "mdi:thermostat-auto"),
          badge(e.hvacControllerActive, "Controller", "mdi:shield-lock-outline"),
          badge(e.batterySoc, "Battery", "mdi:battery-high"),
          badge(e.livePeakImportRisk, "Import risk", "mdi:transmission-tower-alert"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Peak demand response", "mdi:thermostat-auto"),
              markdown(peakControlsNarrative(e)),
              tile(e.hvacControllerActive, "Controller ownership", "mdi:shield-lock-outline"),
              tile(e.batterySoc, "Battery state of charge", "mdi:battery-high"),
              tile(e.batteryMinutesToReserve, "Conservative minutes to reserve", "mdi:battery-clock-outline"),
              tile(e.peakMinutesRemaining, "Actual peak minutes remaining", "mdi:timer-sand"),
              tile(e.gridImportPower, "Live EG4 grid import", "mdi:transmission-tower-import"),
              tile(e.peakForecastShortfall, "Forecast shortfall", "mdi:battery-clock-outline"),
              tile(e.livePeakImportRisk, "Sustained import risk", "mdi:transmission-tower-alert"),
              {
                type: "entities",
                title: "Live thermostat targets",
                show_header_toggle: false,
                entities: [
                  row(e.downstairsClimate, "Downstairs"),
                  row(e.primaryClimate, "Primary bedroom"),
                  row(e.upstairsClimate, "Upstairs"),
                ],
                grid_options: { columns: "full", rows: 3 },
              },
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Configure the rule", "mdi:tune-vertical"),
              {
                type: "entities",
                title: "Master, timing, and thresholds",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.hvacResponseEnabled, "Enable automatic A/C response"),
                  row(e.hvacWindowStart, "Alert/response start"),
                  row(e.hvacWindowEnd, "Alert/response end"),
                  row(e.hvacSocGuardrail, "Forecast SOC guardrail"),
                  row(e.hvacSetpointIncrease, "Cooling setpoint increase"),
                  row(e.hvacRestoreEnabled, "Restore still-owned targets"),
                  row(e.peakImportThreshold, "Sustained import threshold"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              {
                type: "entities",
                title: "Zone participation and comfort caps",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.hvacEastEnabled, "Downstairs enabled"),
                  row(e.hvacEastMaximum, "Downstairs maximum"),
                  row(e.hvacWestEnabled, "Primary bedroom enabled"),
                  row(e.hvacWestMaximum, "Primary bedroom maximum"),
                  row(e.hvacUpstairsEnabled, "Upstairs enabled"),
                  row(e.hvacUpstairsMaximum, "Upstairs maximum"),
                ],
                grid_options: { columns: "full", rows: 6 },
              },
              markdown(peakControlsSafety(e)),
              markdown(peakControlsAudit(e)),
            ],
          },
        ],
      }),
      sectionsView({
        title: "Diagnostics",
        path: "diagnostics",
        icon: "mdi:stethoscope",
        badges: [
          badge(e.measurementModelValid, "Model", "mdi:check-decagram-outline"),
          badge(e.telemetryHealthy, "Telemetry", "mdi:heart-pulse"),
          badge(e.tigoModuleProblem, "Tigo", "mdi:view-grid-outline"),
          badge(e.srpIntegrationAvailable, "SRP", "mdi:cloud-check-outline"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Model health", "mdi:check-decagram-outline"),
              markdown(diagnosticsNarrative(e)),
              {
                type: "entities",
                title: "Quality gates",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.measurementModelValid, "AC-bus equation valid"),
                  row(e.telemetryHealthy, "Required telemetry healthy"),
                  row(e.sourceHealth, "Overall source health"),
                  row(e.gridReconciliationMatches, "SRP / EG4 daily net match"),
                  row(e.srpIntegrationAvailable, "SRP integration available"),
                  row(e.enphaseSystemProblem, "Enphase system problem"),
                  row(e.tigoModuleProblem, "Tigo module problem"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              {
                type: "entity-filter",
                state_filter: ["unknown", "unavailable"],
                show_empty: false,
                entities: [
                  e.combinedSolarPower,
                  e.wholeHomeLoad,
                  e.gridNetPower,
                  e.batterySoc,
                  e.batteryMinutesToReserve,
                  e.srpSettledNetEnergy,
                  e.tigoArrayPower,
                ],
                card: { type: "entities", title: "Unavailable calculated telemetry", show_header_toggle: false },
                grid_options: { columns: "full" },
              },
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Auditable measurement contract", "mdi:function-variant"),
              markdown(`### Live balance
**Whole-home load** = EG4 AC + Enphase AC + signed grid − rectifier

Equivalent cross-check: EG4 vendor-calculated load + Enphase AC

### Solar
**Combined solar estimate** = EG4 PV DC + Enphase AC

Tigo is excluded because it observes the same EG4 panels.

### Grid
**Import** = max(signed grid, 0)

**Export** = max(−signed grid, 0)

### Battery
**User-facing battery power** = −EG4 raw battery power

Positive means discharge; negative means charge.

### Daily utility check
Sum raw SRP hourly net intervals, then compare with EG4 daily import change minus export change.`),
              markdown(`## Equipment pages
[EG4 solar & battery](/eg4-energy/live) · [Enphase array](/enphase-2103/overview) · [Tigo module map](/tigo-energy/overview) · [SRP billing detail](/srp-energy)`),
            ],
          },
        ],
      }),
    ],
  };
}

export const dashboardMetadata = Object.freeze({
  urlPath: "home-energy",
  title: "Home Energy",
  icon: "mdi:home-lightning-bolt",
  showInSidebar: true,
  requireAdmin: false,
});
