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
    sections: sections.map((section) => ({
      ...section,
      cards: section.cards.map((card) => {
        if (card.type !== "entities" || !card.grid_options?.rows) return card;
        // Let entity rows grow with mobile inputs instead of trapping controls
        // inside a second, clipped scrolling area.
        const { rows: _rows, ...gridOptions } = card.grid_options;
        return { ...card, grid_options: gridOptions };
      }),
    })),
  };
}

function wholeHomeNarrative(e) {
  return `{% set load = states('${e.wholeHomeLoad}') %}
{% set grid = states('${e.gridNetPower}') %}
{% set battery = states('${e.batteryNetPower}') %}
{% if not is_state('${e.measurementModelValid}', 'on') or not is_number(load) %}
**Whole-home load is unavailable.** A required source is missing, stale, or inconsistent. The separate grid and battery readings remain useful when their own feeds are fresh. See **Diagnostics**.
{% else %}
The home is using **{{ ((load | float) / 1000) | round(1) }} kW**, including the EG4 backup circuits and main-panel circuits.

{% if is_number(grid) %}{% if grid | float > 50 %}SRP is supplying **{{ ((grid | float) / 1000) | round(1) }} kW**.{% elif grid | float < -50 %}The property is exporting **{{ ((grid | float | abs) / 1000) | round(1) }} kW** to SRP.{% else %}Grid exchange is near zero.{% endif %}{% endif %} {% if is_number(battery) %}{% if battery | float > 50 %}The battery is discharging **{{ ((battery | float) / 1000) | round(1) }} kW**.{% elif battery | float < -50 %}The battery is charging **{{ ((battery | float | abs) / 1000) | round(1) }} kW**.{% else %}The battery is standing by.{% endif %}{% endif %}
{% if state_attr('${e.wholeHomeLoad}', 'enphase_cloud_fallback') %}
**Estimate:** local Envoy is unavailable; this calculation uses a delayed Enphase cloud sample.
{% endif %}
{% endif %}`;
}

function solarNarrative(_e) {
  return `**Two separate arrays.** EG4 reports panel-side DC power; the local Envoy reports the Enphase array's AC power. Their sum is a solar estimate because inverter conversion losses have not been removed.

**Every EG4 panel has a Tigo optimizer.** Tigo measures the same panels and is a diagnostic comparison, never extra production. C4 is the known module outage.

EG4 also supplies its own backup loads before power reaches the main panel. The utility CTs measure the complete property's net import or export.`;
}

function liveFlow(e) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 650">
<rect width="800" height="650" rx="24" fill="#101b2c"/>
<g fill="none" stroke="#42546d" stroke-width="5" stroke-linejoin="round">
<path d="M130 114V150H360V188"/><path d="M220 248H300"/>
<path d="M500 248H580"/><path d="M400 306V430"/>
<path d="M670 114H790V430H400"/>
<path d="M220 430H400V530"/>
</g>
<g stroke-width="2">
<rect x="20" y="24" width="220" height="90" rx="16" fill="#28301e" stroke="#b29442"/>
<rect x="560" y="24" width="220" height="90" rx="16" fill="#142d41" stroke="#3986aa"/>
<rect x="300" y="188" width="200" height="118" rx="16" fill="#24344a" stroke="#8199b7"/>
<rect x="20" y="196" width="200" height="110" rx="16" fill="#20372f" stroke="#48a88b"/>
<rect x="580" y="196" width="200" height="110" rx="16" fill="#253044" stroke="#667d9a"/>
<rect x="20" y="378" width="200" height="110" rx="16" fill="#2c2843" stroke="#9a86c8"/>
<rect x="300" y="530" width="200" height="96" rx="16" fill="#253044" stroke="#667d9a"/>
</g>
<g fill="#edf3fc" text-anchor="middle" font-family="Arial,sans-serif" font-size="25">
<text x="130" y="55">EG4 panels · DC</text><text x="670" y="55">Enphase array · AC</text>
<text x="400" y="231">EG4 inverter</text><text x="400" y="272" font-size="22">Solar + battery</text>
<text x="120" y="226">Battery</text><text x="680" y="231">Backup loads</text>
<text x="680" y="271" fill="#aebed3" font-size="23">Unmetered</text>
<text x="120" y="411">SRP meter / CT</text>
<text x="400" y="565">Main-panel loads</text><text x="400" y="602" fill="#aebed3" font-size="23">Unmetered</text>
<text x="478" y="463" fill="#aebed3" font-size="22">Shared AC connection</text>
</g></svg>`;
  function label(entity, left, top, extra = {}) {
    return {
      type: "state-label", entity,
      style: { left: `${left}%`, top: `${top}%`, color: "#ffffff", "font-size": "clamp(11px, 1.1vw, 17px)", "font-weight": "600" },
      ...extra, ...noActions(),
    };
  }
  function arrow(entity, direction, left, top, above, below, color) {
    return {
      type: "conditional",
      conditions: [{ condition: "numeric_state", entity, ...(above != null ? { above } : {}), ...(below != null ? { below } : {}) }],
      elements: [{ type: "icon", icon: `mdi:arrow-${direction}-bold`, style: { left: `${left}%`, top: `${top}%`, color, "--mdc-icon-size": "28px" }, ...noActions() }],
    };
  }
  return {
    type: "picture-elements",
    image: `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`,
    elements: [
      label(e.combinedSolarPower, 16.25, 13.5, { attribute: "eg4_pv_power_w", suffix: " W" }),
      label(e.combinedSolarPower, 83.75, 13.5, { attribute: "enphase_power_w", suffix: " W" }),
      label(e.batteryNetPower, 15, 40.5),
      label(e.batterySoc, 15, 44.5, { suffix: " remaining" }),
      label(e.gridNetPower, 15, 68.5),
      arrow(e.batteryNetPower, "right", 32.5, 38.2, 50, null, "#67d3a7"),
      arrow(e.batteryNetPower, "left", 32.5, 38.2, null, -50, "#67d3a7"),
      arrow(e.gridNetPower, "right", 32.5, 66.15, 50, null, "#c1a7f4"),
      arrow(e.gridNetPower, "left", 32.5, 66.15, null, -50, "#c1a7f4"),
    ],
    grid_options: { columns: "full" },
  };
}

function reconciliationNarrative(e) {
  return `{% set residual = states('${e.gridReconciliationResidual}') %}
{% if is_number(residual) %}
**{{ states('${e.gridReconciliationDate}') }}:** EG4 minus SRP is **{{ (residual | float) | round(2) }} kWh**. {{ 'Within' if is_state('${e.gridReconciliationMatches}', 'on') else 'Outside' }} the configured **{{ state_attr('${e.gridReconciliationResidual}', 'tolerance_kwh') }} kWh** tolerance.

**Net energy only.** Both sources need 24 distinct valid hours in Arizona time. The allowance is the larger of 1 kWh or 2% of the larger absolute net reading.

Separate SRP import and export have not been validated. Gross-flow percentages are context, not separate directional agreement. The newest complete day may still be revised by SRP; a match does not establish CT calibration.
{% else %}
A complete net-energy comparison is unavailable. {{ state_attr('${e.gridReconciliationResidual}', 'refresh_error') or 'Waiting for a common day with 24 valid hours from each meter.' }}
{% endif %}`;
}

function batteryForecast(e) {
  return `{% set valid = state_attr('${e.batteryMinutesToReserve}', 'forecast_valid') %}
{% set at_reserve = is_state('${e.batteryAtReserve}', 'on') %}
{% if at_reserve %}
## 🪫 Battery is at its commissioned reserve
State of charge is **{{ states('${e.batterySoc}') }}%**. The EG4 normally stops supplementing the home at this 20% floor.
{% elif valid %}
## 🔋 Reserve forecast
About **{{ states('${e.batteryAvailableEnergy}') }} kWh** remains above reserve. Recent average use gives **{{ state_attr('${e.batteryMinutesToReserve}', 'central_minutes') | round(0) if state_attr('${e.batteryMinutesToReserve}', 'central_minutes') is number else 'unavailable' }} minutes**; the conservative planning case gives **{{ states('${e.batteryMinutesToReserve}') }} minutes**.

A household shortfall warning needs both estimates to run out before peak ends. The conservative case still protects the cooling response.
{% else %}
## ⏳ Building a reliable forecast
The forecast needs at least five fresh discharge samples spanning eight minutes. It stays unavailable while the battery is charging or telemetry is stale.
{% endif %}`;
}

function peakNarrative(e) {
  return `{% set peak = is_state('${e.peakWindow}', 'on') %}
{% set schedule_ok = is_state('${e.peakScheduleValid}', 'on') %}
{% set central = state_attr('${e.batteryMinutesToReserve}', 'central_minutes') %}
{% set conservative = state_attr('${e.batteryMinutesToReserve}', 'conservative_minutes') %}
{% set remaining = states('${e.peakMinutesRemaining}') %}
{% set household_short = state_attr('${e.batteryMinutesToReserve}', 'forecast_valid') == true
   and central is number and conservative is number and is_number(remaining)
   and 0 <= central <= remaining | float and 0 <= conservative <= remaining | float %}
{% if not schedule_ok %}
## ⚠️ Peak schedule needs attention
The peak model fails safe when the editable SRP schedule is invalid.
{% elif not peak %}
## ✅ Off peak
Profile: **{{ states('${e.peakProfile}') }}**. Battery and grid are monitored continuously; demand alerts arm only during the configured peak window.
{% elif is_state('${e.livePeakImportRisk}', 'on') %}
## 🚨 On peak · material grid import
Live import is **{{ (states('${e.gridImportPower}') | float / 1000) | round(1) }} kW**, above the **{{ states('${e.peakImportThreshold}') }} kW** alert threshold. Sustained import can raise billed demand.
{% elif household_short %}
## ⚠️ On peak · battery shortfall forecast
Both forecasts reach reserve before peak ends: **{{ central | round(0) }} minutes** at recent average use and **{{ conservative | round(0) }} minutes** in the planning case, with **{{ remaining }} peak minutes** left.
{% else %}
## 🛡️ {{ states('${e.peakStrategyStatus}') }}
The grid and battery readings remain under observation. A conservative planning warning alone does not mean the battery will run out.
{% endif %}`;
}

function climateRecommendation(e) {
  return `**Peak cooling response:** {{ 'enabled' if is_state('${e.hvacResponseEnabled}', 'on') else 'disabled' }}. It follows both winter SRP windows and the summer window, and acts only while the family is home.

A battery shortfall at or below the SOC guardrail, or five minutes of high grid import, can raise selected cooling targets within their caps. The separate comfort schedule handles seasonal heating/cooling, bedtime, arrival, and away settings.

- **Downstairs:** {{ state_attr('${e.downstairsClimate}', 'current_temperature') }}° → {{ state_attr('${e.downstairsClimate}', 'temperature') }}°
- **Primary bedroom:** {{ state_attr('${e.primaryClimate}', 'current_temperature') }}° → {{ state_attr('${e.primaryClimate}', 'temperature') }}°
- **Upstairs:** {{ state_attr('${e.upstairsClimate}', 'current_temperature') }}° → {{ state_attr('${e.upstairsClimate}', 'temperature') }}°`;
}

function peakControlsNarrative(e) {
  return `**{{ 'Responding to peak risk' if is_state('${e.hvacControllerActive}', 'on') else 'Standing by' }}** · automatic response {{ 'enabled' if is_state('${e.hvacResponseEnabled}', 'on') else 'disabled' }}

**Timing:** every valid active SRP peak, including both winter windows. **Forecast guardrail:** {{ states('${e.hvacSocGuardrail}') }}% battery charge. **Cooling increase:** up to {{ states('${e.hvacSetpointIncrease}') }}°F.

{% if is_state('${e.hvacControllerActive}', 'on') %}
{{ states('${e.hvacControllerStatus}') if states('${e.hvacControllerStatus}') not in ['unknown', 'unavailable', ''] else 'Adjusting eligible cooling targets.' }}
{% elif not is_state('${e.hvacResponseEnabled}', 'on') %}
Automatic cooling response is off.
{% elif not is_state('group.family_presence', 'home') %}
Waiting until the family is home.
{% elif is_state('${e.peakWindow}', 'on') and is_state('${e.peakScheduleValid}', 'on') %}
No risk adjustment is active for this peak.
{% else %}
No SRP peak response is active.
{% endif %}

Only occupied-home cooling targets are eligible. This risk response does not change thermostat modes; the comfort schedule handles winter heating setbacks.`;
}

function peakControlsSafety(_e) {
  return `**Target ownership** prevents the risk response from undoing your changes.

- Each zone is captured before its target is raised, within the zone and thermostat limits.
- A manual or scheduled change releases that zone.
- Leaving home, disabling response, an invalid schedule, or the end of SRP peak releases the response.
- Restoration changes only a target that still exactly matches the response's applied value.
- The controller reports inactive after restoration finishes, so the comfort schedule can safely take over.
- Each winter morning/evening window can respond once. The saved event survives automation reloads.`;
}

function peakControlsAudit(e) {
  return `**Saved response note:** {{ states('${e.hvacControllerStatus}') if states('${e.hvacControllerStatus}') not in ['unknown', 'unavailable', ''] else 'No response recorded.' }}
{% if states('${e.hvacControllerStatus}') not in ['unknown', 'unavailable', ''] %}
Updated {{ as_timestamp(states['${e.hvacControllerStatus}'].last_changed) | timestamp_custom('%b %-d, %-I:%M %p') }}.
{% endif %}

**Last handled period:** {{ states('${e.hvacControllerEventKey}') }}

**Owned targets:** downstairs {{ states('${e.hvacEastOwned}') }}, primary bedroom {{ states('${e.hvacWestOwned}') }}, upstairs {{ states('${e.hvacUpstairsOwned}') }}.

The old 6–8 PM helper values are retained for existing references and no longer control timing.`;
}

function diagnosticsNarrative(e) {
  return `{% set issues = state_attr('${e.sourceHealth}', 'issues') or [] %}
**Source health:** {{ states('${e.sourceHealth}') }}. **Internal AC-bus consistency:** {{ 'within tolerance' if is_state('${e.measurementModelValid}', 'on') else 'unavailable or outside tolerance' }}.

The consistency equation reuses EG4's calculated consumption; it is not an independent measurement of either panel's load or proof that the utility meter agrees.

{% if issues %}{% for issue in issues %}- {{ issue }}
{% endfor %}{% else %}No source issues reported.{% endif %}`;
}

export function buildDashboard(discovery) {
  const e = {
    ...discovery.entities,
    inverterScheduleStatus: "sensor.home_energy_inverter_schedule_status",
    srpPeriod: "sensor.home_energy_srp_period",
    automaticInverterSchedule: "switch.home_energy_automatic_inverter_schedule",
  };
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
              heading("Live energy flow", "mdi:chart-sankey-variant"),
              liveFlow(e),
              markdown(wholeHomeNarrative(e)),
              markdown("Arrows follow fresh signed battery and grid power. Backup loads and main-panel loads are shown in their physical branches; their separate wattages are not measured."),
              heading("Current power", "mdi:flash", "subtitle"),
              tile(e.combinedSolarPower, "Solar estimate", "mdi:solar-power"),
              tile(e.wholeHomeLoad, "Home load", "mdi:home-lightning-bolt"),
              tile(e.gridImportPower, "Grid import", "mdi:transmission-tower-import"),
              tile(e.gridExportPower, "Grid export", "mdi:transmission-tower-export"),
              tile(e.batteryNetPower, "Battery power", "mdi:battery-sync"),
              tile(e.batterySoc, "Battery charge", "mdi:battery-high"),
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
                  row(e.combinedSolarPower, "Solar estimate"),
                  row(e.wholeHomeLoad, "Home load"),
                  row(e.gridNetPower, "Grid net · + import / − export"),
                  row(e.batteryNetPower, "Battery · + discharge / − charge"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              heading("How to read these values", "mdi:information-outline", "subtitle"),
              markdown(`- **Measured:** EG4 whole-property grid CT, battery SOC, source-device telemetry.
- **Derived:** whole-home load and AC balance.
- **Estimated:** combined solar mixes EG4 DC and Enphase AC.
- **Utility settled:** delayed SRP billing data.

The backup-panel and regular-panel loads **cannot be separated** with the installed sensors. Separate backup-panel and main-panel readings require dedicated submeters.`),
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
                title: "Array readings · DC and AC",
                entities: [
                  { entity: e.eg4PvPower, name: "EG4 array · DC", color: "#f9a825" },
                  { entity: e.enphasePower, name: "Enphase array · AC", color: "#1e88e5" },
                ],
                grid_options: { columns: "full" },
              },
              tile(e.eg4PvPower, "EG4 PV · measured DC", "mdi:solar-panel"),
              tile(e.enphasePower, "Enphase · measured AC", "mdi:solar-panel-large"),
              tile(e.combinedSolarPower, "Combined · estimated", "mdi:solar-power", 12),
              markdown(`**EG4** · DC input: {{ states('${e.eg4PvPower}') }} {{ state_attr('${e.eg4PvPower}', 'unit_of_measurement') }}. [Inverter and battery detail](/eg4-energy/live).

{% set sample = state_attr('${e.combinedSolarPower}', 'enphase_sample_at') %}
**Enphase** · {{ state_attr('${e.combinedSolarPower}', 'enphase_power_source') or 'unavailable' }}. Sample {{ as_timestamp(sample) | timestamp_custom('%-I:%M %p') if sample else 'unavailable' }}. Local Envoy is authoritative; cloud scope remains unverified and automatic fallback is disabled by default. Lifetime energy always retains its original local Envoy history. [Microinverter detail](/enphase-2103/overview).

{% set age = state_attr('${e.tigoRatio}', 'sample_age_minutes') %}
{% set skew = state_attr('${e.tigoRatio}', 'alignment_skew_seconds') %}
**Tigo** · {{ state_attr('${e.tigoRatio}', 'comparison_reason') or 'Waiting for a fresh sample' }}. Sample age {{ ((age | round(1)) ~ ' min') if age is number else 'unavailable' }}; alignment {{ ((skew | round(0)) ~ ' seconds') if skew is number else 'unavailable' }}. The ratio expires when the cloud sample expires. [Module map](/tigo-energy/overview).`),
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Array diagnostics", "mdi:stethoscope"),
              {
                type: "entities",
                title: "Tigo and Enphase health",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.tigoModuleProblem, "Tigo modules · C4 known down"),
                  row(e.tigoArrayPower, "Tigo diagnostic power · not additive"),
                  row(e.tigoAlignedEg4Power, "EG4 power aligned to Tigo sample"),
                  row(e.tigoRatio, "Tigo / EG4 · time-aligned ratio"),
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
                  row(e.tigoArrayPower, "Tigo · same EG4 panels"),
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
              tile(e.batteryNetPower, "Battery power", "mdi:battery-sync"),
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
          badge(e.gridReconciliationMatches, "Meter comparison", "mdi:scale-balance"),
          badge(e.srpIntegrationAvailable, "SRP feed", "mdi:cloud-check-outline"),
          badge(e.srpBilledCyclePeak, "Reported maximum", "mdi:chart-timeline-variant"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Live utility boundary", "mdi:meter-electric-outline"),
              markdown(`The EG4 current transformers (CTs) are on the incoming SRP service lines. They measure net exchange for both arrays, both panels, and the battery. **Positive = import; negative = export.** Compare their accumulated net energy with SRP settled intervals to check agreement.`),
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
              heading("Daily meter comparison", "mdi:scale-balance"),
              markdown(reconciliationNarrative(e)),
              {
                type: "entities",
                title: "Latest complete net comparison · may revise",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.gridReconciliationDate, "Comparison date"),
                  row(e.srpSettledNetEnergy, "SRP net · delayed"),
                  row(e.eg4SameDayNetEnergy, "EG4 CT net"),
                  row(e.gridReconciliationResidual, "EG4 minus SRP residual"),
                  row(e.gridReconciliationMatches, "Net within configured tolerance"),
                ],
                grid_options: { columns: "full", rows: 5 },
              },
              markdown("This comparison uses SRP's signed **net** intervals; the separate production and usage fields are not independent meters for either solar array."),
            ],
          },
          {
            type: "grid",
            cards: [
              heading("Demand & billing", "mdi:finance"),
              ...(e.srpDemandAudit ? [{
                ...tile(e.srpDemandAudit, "Daily demand check", "mdi:check-decagram-outline", 12),
                tap_action: { action: "more-info" },
                icon_tap_action: { action: "more-info" },
              }] : []),
              markdown(e.srpDemandAudit
                ? "The demand check compares SRP's daily maximum with its half-hour readings. Missing readings stay incomplete. Tap the check for the date and winning half-hour."
                : "The demand check is unavailable. Open SRP detail to review its data."),
              tile(e.srpCurrentDemand, "Current-cycle demand · delayed", "mdi:gauge"),
              tile(e.srpBilledCyclePeak, "Reported cycle maximum · delayed", "mdi:chart-line"),
              tile(e.srpBillProjection, "Bill projection · delayed", "mdi:cash-clock", 12),
              markdown("The cycle maximum and average daily demand are different measures. Billed dollar line items are not imported; the projection estimates the whole bill, not the demand charge. [Open SRP detail](/srp-energy)"),
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
          badge(e.peakForecastShortfall, "Conservative guard", "mdi:battery-clock-outline"),
          badge(e.livePeakImportRisk, "Import risk", "mdi:transmission-tower-alert"),
        ],
        sections: [
          {
            type: "grid",
            cards: [
              heading("Live peak posture", "mdi:shield-home"),
              markdown(peakNarrative(e)),
              tile(e.srpPeriod, "Current SRP period", "mdi:calendar-clock", 12),
              tile(e.inverterScheduleStatus, "EG4 schedule readback", "mdi:calendar-check", 12),
              {
                type: "entities", title: "Battery schedule", show_header_toggle: false,
                entities: [{ entity: e.automaticInverterSchedule, name: "Automatic EG4 schedule" }],
                grid_options: { columns: "full" },
              },
              markdown("Automatic scheduling follows SRP seasons, weekends and holidays. Turning it off stops further changes and leaves the inverter's last applied schedule in place."),
              markdown(`{% set verified = state_attr('${e.inverterScheduleStatus}', 'last_verified') %}
**Schedule profile:** {{ state_attr('${e.inverterScheduleStatus}', 'profile') or 'Not verified' }}. **Last verified:** {{ as_timestamp(verified) | timestamp_custom('%b %-d, %-I:%M %p') if verified else 'Not yet verified' }}.

{{ state_attr('${e.inverterScheduleStatus}', 'error') or '' }}

A schedule readback confirms settings. Check the battery and grid graphs to verify actual discharge.`),
              tile(e.peakStrategyStatus, "Peak strategy", "mdi:shield-home-outline", 12),
              tile(e.peakMinutesRemaining, "Minutes left in peak window", "mdi:timer-sand"),
              tile(e.batteryMinutesToReserve, "Conservative minutes to reserve", "mdi:battery-clock-outline"),
              tile(e.gridImportPower, "Live grid import", "mdi:transmission-tower-import"),
              tile(e.srpBilledCyclePeak, "SRP cycle maximum · delayed", "mdi:chart-timeline-variant"),
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
              heading("Planning inputs", "mdi:tune-variant", "subtitle"),
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
              markdown(`Family alerts cover battery reserve, a shortfall in both forecasts, and five minutes of high peak import. Four additional Home Assistant notices flag missing peak battery support, unusable EG4 readings, scheduling faults, or a mismatched pre-peak profile. Those notices report a problem; they do not change equipment.`),
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
              tile(e.batterySoc, "Battery charge", "mdi:battery-high"),
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
                title: "Master and thresholds",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.hvacResponseEnabled, "Enable automatic A/C response"),

                  row(e.hvacSocGuardrail, "Forecast SOC guardrail"),
                  row(e.hvacSetpointIncrease, "Cooling setpoint increase"),
                  row(e.hvacRestoreEnabled, "Restore still-owned targets"),
                  row(e.peakImportThreshold, "Import threshold"),
                ],
                grid_options: { columns: "full", rows: 7 },
              },
              {
                type: "entities",
                title: "Cooling zones",
                show_header_toggle: false,
                state_color: true,
                entities: [
                  row(e.hvacEastEnabled, "Downstairs enabled"),
                  row(e.hvacEastMaximum, "Downstairs maximum"),
                  row(e.hvacWestEnabled, "Primary enabled"),
                  row(e.hvacWestMaximum, "Primary maximum"),
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
                  row(e.measurementModelValid, "Internal AC-bus consistency"),
                  row(e.telemetryHealthy, "Required telemetry healthy"),
                  row(e.sourceHealth, "Overall source health"),
                  row(e.gridReconciliationMatches, "SRP / EG4 net within tolerance"),
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
              heading("HA report age", "mdi:timer-outline"),
              markdown(`{% set ages = state_attr('${e.sourceHealth}', 'source_ages_minutes') or {} %}
{% for name in ages %}{% set age = ages[name] %}- **{{ name }}:** {{ (age | round(1)) ~ ' min' if age is number else 'unavailable' }}
{% endfor %}
These are Home Assistant report ages, not vendor-frame ages. Repeated reports can contain an older measurement.`),
              heading("Auditable measurement contract", "mdi:function-variant"),
              markdown(`### Live balance
**Whole-home load** = EG4 AC + Enphase AC + signed grid − rectifier

Equivalent identity: EG4 vendor-calculated load + Enphase AC. This reuses the same inverter measurements and is not independent calibration.

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
Compare net energy only, using 24 distinct valid hourly intervals from each source. The allowance is the larger of 1 kWh or 2% of the larger absolute net reading. Separate utility import and export remain unvalidated; the newest complete day may still be revised.`),
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
