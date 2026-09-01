import { peakControlDefaults } from "./peak-controls.mjs";

export const helperSpecifications = Object.freeze([
  {
    domain: "input_number",
    id: "home_energy_battery_capacity_kwh",
    defaultState: 28,
    config: {
      name: "Home Energy Battery Capacity kWh",
      icon: "mdi:battery-high",
      min: 1,
      max: 100,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kWh",
    },
  },
  {
    domain: "input_number",
    id: "home_energy_battery_reserve_percent",
    defaultState: 20,
    config: {
      name: "Home Energy Battery Reserve Percent",
      icon: "mdi:battery-alert-variant-outline",
      min: 0,
      max: 50,
      step: 1,
      mode: "box",
      unit_of_measurement: "%",
    },
  },
  {
    domain: "input_number",
    id: "home_energy_peak_import_threshold_kw",
    defaultState: 5,
    config: {
      name: "Home Energy Peak Import Threshold kW",
      icon: "mdi:transmission-tower-import",
      min: 0.5,
      max: 25,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kW",
    },
  },
  {
    domain: "input_number",
    id: "home_energy_planning_discharge_kw",
    defaultState: 7,
    config: {
      name: "Home Energy Planning Discharge kW",
      icon: "mdi:battery-clock-outline",
      min: 0.5,
      max: 25,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kW",
    },
  },
  {
    domain: "input_text",
    id: "home_energy_reserve_alert_key",
    config: {
      name: "Home Energy Reserve Alert Key",
      icon: "mdi:message-badge-outline",
      min: 0,
      max: 64,
      mode: "text",
    },
  },
  {
    domain: "input_text",
    id: "home_energy_forecast_alert_key",
    config: {
      name: "Home Energy Forecast Alert Key",
      icon: "mdi:message-badge-outline",
      min: 0,
      max: 64,
      mode: "text",
    },
  },
  {
    domain: "input_text",
    id: "home_energy_peak_import_alert_key",
    config: {
      name: "Home Energy Peak Import Alert Key",
      icon: "mdi:message-badge-outline",
      min: 0,
      max: 64,
      mode: "text",
    },
  },
  {
    domain: "input_boolean",
    id: "home_energy_hvac_response_enabled",
    defaultState: false,
    config: {
      name: "Home Energy HVAC Response Enabled",
      icon: "mdi:thermostat-auto",
    },
  },
  {
    domain: "input_datetime",
    id: "home_energy_hvac_window_start",
    defaultState: peakControlDefaults.windowStart,
    config: {
      name: "Home Energy HVAC Window Start",
      icon: "mdi:clock-start",
      has_date: false,
      has_time: true,
    },
  },
  {
    domain: "input_datetime",
    id: "home_energy_hvac_window_end",
    defaultState: peakControlDefaults.windowEnd,
    config: {
      name: "Home Energy HVAC Window End",
      icon: "mdi:clock-end",
      has_date: false,
      has_time: true,
    },
  },
  {
    domain: "input_number",
    id: "home_energy_hvac_soc_guardrail_percent",
    defaultState: peakControlDefaults.socGuardrailPercent,
    config: {
      name: "Home Energy HVAC SOC Guardrail Percent",
      icon: "mdi:battery-alert",
      min: 20,
      max: 60,
      step: 1,
      mode: "box",
      unit_of_measurement: "%",
    },
  },
  {
    domain: "input_number",
    id: "home_energy_hvac_setpoint_increase_f",
    defaultState: peakControlDefaults.setpointIncreaseF,
    config: {
      name: "Home Energy HVAC Setpoint Increase F",
      icon: "mdi:thermometer-plus",
      min: 0.5,
      max: 6,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "°F",
    },
  },
  ...[
    ["east", "East", "mdi:home-floor-1"],
    ["west", "West", "mdi:bed-king-outline"],
    ["upstairs", "Upstairs", "mdi:home-floor-2"],
  ].flatMap(([key, label, icon]) => [
    {
      domain: "input_boolean",
      id: `home_energy_hvac_${key}_zone_enabled`,
      defaultState: true,
      config: {
        name: `Home Energy HVAC ${label} Zone Enabled`,
        icon,
      },
    },
    {
      domain: "input_number",
      id: `home_energy_hvac_${key}_maximum_f`,
      defaultState: peakControlDefaults.zoneMaximumF,
      config: {
        name: `Home Energy HVAC ${label} Maximum F`,
        icon: "mdi:thermometer-chevron-up",
        min: 70,
        max: 90,
        step: 0.5,
        mode: "box",
        unit_of_measurement: "°F",
      },
    },
  ]),
  {
    domain: "input_boolean",
    id: "home_energy_hvac_restore_enabled",
    defaultState: true,
    config: {
      name: "Home Energy HVAC Restore Enabled",
      icon: "mdi:backup-restore",
    },
  },
  {
    domain: "input_boolean",
    id: "home_energy_hvac_controller_active",
    defaultState: false,
    config: {
      name: "Home Energy HVAC Controller Active",
      icon: "mdi:thermostat-auto",
    },
  },
  {
    domain: "input_text",
    id: "home_energy_hvac_controller_event_key",
    config: {
      name: "Home Energy HVAC Controller Event Key",
      icon: "mdi:key-clock",
      min: 0,
      max: 64,
      mode: "text",
    },
  },
  {
    domain: "input_text",
    id: "home_energy_hvac_controller_status",
    config: {
      name: "Home Energy HVAC Controller Status",
      icon: "mdi:list-status",
      min: 0,
      max: 255,
      mode: "text",
    },
  },
  ...[
    ["east", "East"],
    ["west", "West"],
    ["upstairs", "Upstairs"],
  ].flatMap(([key, label]) => [
    {
      domain: "input_number",
      id: `home_energy_hvac_${key}_previous_f`,
      defaultState: 0,
      config: {
        name: `Home Energy HVAC ${label} Previous F`,
        icon: "mdi:thermometer-chevron-down",
        min: 0,
        max: 100,
        step: 0.5,
        mode: "box",
        unit_of_measurement: "°F",
      },
    },
    {
      domain: "input_number",
      id: `home_energy_hvac_${key}_applied_f`,
      defaultState: 0,
      config: {
        name: `Home Energy HVAC ${label} Applied F`,
        icon: "mdi:thermometer-check",
        min: 0,
        max: 100,
        step: 0.5,
        mode: "box",
        unit_of_measurement: "°F",
      },
    },
    {
      domain: "input_boolean",
      id: `home_energy_hvac_${key}_owned`,
      defaultState: false,
      config: {
        name: `Home Energy HVAC ${label} Owned`,
        icon: "mdi:shield-lock-outline",
      },
    },
  ]),
]);

const notifyFamily = (title, message, latch, alertKey = "{{ alert_key }}") => [
  {
    action: "persistent_notification.create",
    data: {
      title,
      message,
      notification_id: "{{ this.entity_id | replace('automation.', '') }}",
    },
  },
  {
    action: "script.notify_family",
    continue_on_error: true,
    data: { title, message },
  },
  {
    action: "input_text.set_value",
    target: { entity_id: latch },
    data: { value: alertKey },
  },
];

function peakControlWindowTemplate(e) {
  return `{% set bad = ['unknown', 'unavailable', 'none', ''] %}
{% set start_text = states('${e.hvacWindowStart}') %}
{% set end_text = states('${e.hvacWindowEnd}') %}
{% if start_text in bad or end_text in bad or start_text == end_text %}
  false
{% else %}
  {% set start = today_at(start_text) %}
  {% set end = today_at(end_text) %}
  {{ start <= now() < end if start < end else now() >= start or now() < end }}
{% endif %}`;
}

function peakControlOutsideWindowTemplate(e) {
  return `{% set bad = ['unknown', 'unavailable', 'none', ''] %}
{% set start_text = states('${e.hvacWindowStart}') %}
{% set end_text = states('${e.hvacWindowEnd}') %}
{% if start_text in bad or end_text in bad or start_text == end_text %}
  true
{% else %}
  {% set start = today_at(start_text) %}
  {% set end = today_at(end_text) %}
  {{ not (start <= now() < end) if start < end else not (now() >= start or now() < end) }}
{% endif %}`;
}

function peakControlEndingSoonTemplate(e) {
  return `{% set bad = ['unknown', 'unavailable', 'none', ''] %}
{% set start_text = states('${e.hvacWindowStart}') %}
{% set end_text = states('${e.hvacWindowEnd}') %}
{% if start_text in bad or end_text in bad or start_text == end_text %}
  false
{% else %}
  {% set start = today_at(start_text) %}
  {% set end = today_at(end_text) %}
  {% set in_window = start <= now() < end if start < end else now() >= start or now() < end %}
  {% set window_end = end + timedelta(days=1) if start > end and now() >= start else end %}
  {% set seconds_left = as_timestamp(window_end) - as_timestamp(now()) %}
  {{ in_window and 0 < seconds_left <= 60 }}
{% endif %}`;
}

function peakControlHasActionTimeTemplate(e) {
  return `{% set bad = ['unknown', 'unavailable', 'none', ''] %}
{% set start_text = states('${e.hvacWindowStart}') %}
{% set end_text = states('${e.hvacWindowEnd}') %}
{% if start_text in bad or end_text in bad or start_text == end_text %}
  false
{% else %}
  {% set start = today_at(start_text) %}
  {% set end = today_at(end_text) %}
  {% set in_window = start <= now() < end if start < end else now() >= start or now() < end %}
  {% set window_end = end + timedelta(days=1) if start > end and now() >= start else end %}
  {{ in_window and as_timestamp(window_end) - as_timestamp(now()) > 60 }}
{% endif %}`;
}

function peakControlEventKeyTemplate(e) {
  return `{%- set start_text = states('${e.hvacWindowStart}') -%}
{%- set end_text = states('${e.hvacWindowEnd}') -%}
{%- set overnight = start_text not in ['unknown', 'unavailable', 'none', ''] and end_text not in ['unknown', 'unavailable', 'none', ''] and start_text > end_text -%}
{%- set event_date = (now() - timedelta(days=1)).strftime('%Y-%m-%d') if overnight and now() < today_at(end_text) else now().strftime('%Y-%m-%d') -%}
{{- event_date ~ '-' ~ start_text[:5] ~ '-' ~ end_text[:5] -}}`;
}

function hvacZones(e) {
  return [
    {
      key: "east",
      label: "Downstairs",
      climate: e.downstairsClimate,
      enabled: e.hvacEastEnabled,
      maximum: e.hvacEastMaximum,
      previous: e.hvacEastPrevious,
      applied: e.hvacEastApplied,
      owned: e.hvacEastOwned,
    },
    {
      key: "west",
      label: "Primary bedroom",
      climate: e.primaryClimate,
      enabled: e.hvacWestEnabled,
      maximum: e.hvacWestMaximum,
      previous: e.hvacWestPrevious,
      applied: e.hvacWestApplied,
      owned: e.hvacWestOwned,
    },
    {
      key: "upstairs",
      label: "Upstairs",
      climate: e.upstairsClimate,
      enabled: e.hvacUpstairsEnabled,
      maximum: e.hvacUpstairsMaximum,
      previous: e.hvacUpstairsPrevious,
      applied: e.hvacUpstairsApplied,
      owned: e.hvacUpstairsOwned,
    },
  ];
}

function zoneEligibleTemplate(zone, e) {
  return `{% set current = state_attr('${zone.climate}', 'temperature') %}
{% set climate_max = state_attr('${zone.climate}', 'max_temp') %}
{% set increase = states('${e.hvacSetpointIncrease}') %}
{% set zone_max = states('${zone.maximum}') %}
{{ is_state('${zone.enabled}', 'on')
   and is_state('${zone.climate}', 'cool')
   and current is number and climate_max is number
   and is_number(increase) and is_number(zone_max)
   and (increase | float) > 0
   and [current + (increase | float), zone_max | float, climate_max] | min > current }}`;
}

function zoneTargetTemplate(zone, e) {
  return `{{ [(state_attr('${zone.climate}', 'temperature') | float(0)) + (states('${e.hvacSetpointIncrease}') | float(0)), states('${zone.maximum}') | float(0), state_attr('${zone.climate}', 'max_temp') | float(0)] | min }}`;
}

function zoneStillAtCapturedTargetTemplate(zone) {
  return `{% set current = state_attr('${zone.climate}', 'temperature') %}
{% set previous = states('${zone.previous}') %}
{{ is_state('${zone.owned}', 'on') and current is number and is_number(previous)
   and (current - (previous | float)) | abs <= 0.1 }}`;
}

function controllerStillEligibleConditions(e) {
  return [
    { condition: "state", entity_id: e.hvacControllerActive, state: "on" },
    { condition: "state", entity_id: e.hvacResponseEnabled, state: "on" },
    { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
    { condition: "state", entity_id: e.peakWindow, state: "on" },
    { condition: "template", value_template: peakControlWindowTemplate(e) },
    { condition: "template", value_template: peakControlHasActionTimeTemplate(e) },
  ];
}

function applyZoneAction(zone, e) {
  return {
    choose: [
      {
        conditions: [
          ...controllerStillEligibleConditions(e),
          { condition: "template", value_template: zoneEligibleTemplate(zone, e) },
        ],
        sequence: [
          {
            action: "input_number.set_value",
            target: { entity_id: zone.previous },
            data: { value: `{{ state_attr('${zone.climate}', 'temperature') | float(0) }}` },
          },
          {
            action: "input_number.set_value",
            target: { entity_id: zone.applied },
            data: { value: zoneTargetTemplate(zone, e) },
          },
          { action: "input_boolean.turn_on", target: { entity_id: zone.owned } },
          ...controllerStillEligibleConditions(e),
          { condition: "template", value_template: zoneStillAtCapturedTargetTemplate(zone) },
          {
            action: "climate.set_temperature",
            continue_on_error: true,
            target: { entity_id: zone.climate },
            data: { temperature: `{{ states('${zone.applied}') | float(0) }}` },
          },
          { delay: "00:00:02" },
        ],
      },
    ],
  };
}

function sustainedImportRiskExpression(e) {
  return `is_state('${e.livePeakImportRisk}', 'on')
     and as_timestamp(now()) - as_timestamp(states['${e.livePeakImportRisk}'].last_changed, as_timestamp(now())) >= 300`;
}

function sustainedImportRiskTemplate(e) {
  return `{{ ${sustainedImportRiskExpression(e)} }}`;
}

function releaseZoneAction(zone, e) {
  return {
    choose: [
      {
        conditions: [
          { condition: "state", entity_id: e.hvacRestoreEnabled, state: "on" },
          { condition: "state", entity_id: zone.owned, state: "on" },
          { condition: "state", entity_id: zone.climate, state: "cool" },
          {
            condition: "template",
            value_template: `{% set current = state_attr('${zone.climate}', 'temperature') %}
{% set applied = states('${zone.applied}') %}
{% set previous = states('${zone.previous}') %}
{{ is_state('${zone.owned}', 'on') and current is number and is_number(applied) and is_number(previous)
   and (previous | float) > 0 and (current - (applied | float)) | abs <= 0.1 }}`,
          },
        ],
        sequence: [
          {
            action: "climate.set_temperature",
            continue_on_error: true,
            target: { entity_id: zone.climate },
            data: { temperature: `{{ states('${zone.previous}') | float(0) }}` },
          },
          { delay: "00:00:02" },
        ],
      },
    ],
  };
}

function clearZoneOwnershipAction(zone) {
  return { action: "input_boolean.turn_off", target: { entity_id: zone.owned } };
}

function overrideZoneAction(zone, e) {
  return {
    choose: [
      {
        conditions: [
          { condition: "state", entity_id: zone.owned, state: "on" },
          {
            condition: "template",
            value_template: `{% set current = state_attr('${zone.climate}', 'temperature') %}
{% set applied = states('${zone.applied}') %}
{{ not is_state('${zone.climate}', 'cool')
   or current is not number or not is_number(applied)
   or (current - (applied | float)) | abs > 0.1 }}`,
          },
        ],
        sequence: [
          clearZoneOwnershipAction(zone),
          {
            action: "input_text.set_value",
            target: { entity_id: e.hvacControllerStatus },
            data: {
              value: `${zone.label} was changed outside Peak Controls; ownership released and that zone will not be restored.`,
            },
          },
        ],
      },
    ],
  };
}

function peakHvacActivationConditions(e, zones) {
  return [
    { condition: "state", entity_id: e.hvacResponseEnabled, state: "on" },
    { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
    { condition: "state", entity_id: e.peakWindow, state: "on" },
    { condition: "template", value_template: peakControlWindowTemplate(e) },
    { condition: "template", value_template: peakControlHasActionTimeTemplate(e) },
    { condition: "state", entity_id: e.hvacControllerActive, state: "off" },
    {
      condition: "template",
      value_template: `{{ (is_state('${e.peakForecastShortfall}', 'on')
           and is_number(states('${e.batterySoc}'))
           and is_number(states('${e.hvacSocGuardrail}'))
           and (states('${e.batterySoc}') | float) <= (states('${e.hvacSocGuardrail}') | float))
         or (${sustainedImportRiskExpression(e)}) }}`,
    },
    {
      condition: "template",
      value_template: `{{ states('${e.hvacControllerEventKey}') != event_key }}`,
    },
    {
      condition: "or",
      conditions: zones.map((zone) => ({
        condition: "template",
        value_template: zoneEligibleTemplate(zone, e),
      })),
    },
  ];
}

function peakHvacActivationSequence(e, zones) {
  const anyZoneOwned = {
    condition: "or",
    conditions: zones.map((zone) => ({
      condition: "state",
      entity_id: zone.owned,
      state: "on",
    })),
  };
  return [
    {
      action: "input_text.set_value",
      target: { entity_id: e.hvacControllerEventKey },
      data: { value: "{{ event_key }}" },
    },
    { action: "input_boolean.turn_on", target: { entity_id: e.hvacControllerActive } },
    {
      action: "input_text.set_value",
      target: { entity_id: e.hvacControllerStatus },
      data: { value: "Activating — {{ activation_reason }}; checking each selected cooling zone." },
    },
    ...zones.map((zone) => applyZoneAction(zone, e)),
    { delay: "00:00:01" },
    ...zones.map((zone) => overrideZoneAction(zone, e)),
    {
      choose: [
        {
          conditions: [
            ...controllerStillEligibleConditions(e),
            anyZoneOwned,
          ],
          sequence: [
            {
              action: "input_text.set_value",
              target: { entity_id: e.hvacControllerStatus },
              data: { value: "Active — {{ activation_reason }}; selected zones raised within configured caps." },
            },
            {
              action: "persistent_notification.create",
              data: {
                title: "Home Energy: A/C demand response active",
                notification_id: "home_energy_peak_hvac_response",
                message: `Peak Controls activated for {{ activation_reason }}. The configured increase is {{ states('${e.hvacSetpointIncrease}') }}°F. Downstairs: {{ states('${e.hvacEastApplied}') ~ '°F' if is_state('${e.hvacEastOwned}', 'on') else 'skipped' }}; primary bedroom: {{ states('${e.hvacWestApplied}') ~ '°F' if is_state('${e.hvacWestOwned}', 'on') else 'skipped' }}; upstairs: {{ states('${e.hvacUpstairsApplied}') ~ '°F' if is_state('${e.hvacUpstairsOwned}', 'on') else 'skipped' }}. A later change to a different target releases that zone and will not be overwritten.`,
              },
            },
            {
              action: "script.notify_family",
              continue_on_error: true,
              data: {
                title: "Home Energy: A/C demand response active",
                message: `Peak Controls activated for {{ activation_reason }}. Selected cooling setpoints were raised by up to {{ states('${e.hvacSetpointIncrease}') }}°F within their caps; manual and scheduled changes remain authoritative.`,
              },
            },
          ],
        },
      ],
      default: [
        {
          choose: [
            {
              conditions: [anyZoneOwned],
              sequence: [
                {
                  action: "input_text.set_value",
                  target: { entity_id: e.hvacControllerStatus },
                  data: { value: "Release pending — the rule became ineligible after a partial response; ownership is retained for safe restoration." },
                },
              ],
            },
          ],
          default: [
            { action: "input_boolean.turn_off", target: { entity_id: e.hvacControllerActive } },
            {
              action: "input_text.set_value",
              target: { entity_id: e.hvacControllerStatus },
              data: { value: "Skipped — the rule became ineligible or no selected cooling target could be changed safely." },
            },
          ],
        },
      ],
    },
  ];
}

export function buildAutomations(e) {
  const zones = hvacZones(e);
  return [
    {
      id: "home_energy_battery_reserve_alert",
      config: {
        alias: "Home Energy — battery reached reserve",
        description: "Alerts immediately at the commissioned EG4 reserve, including the exact 20% floor, and again if a peak window starts while already at reserve.",
        triggers: [
          {
            platform: "state",
            entity_id: e.batteryAtReserve,
            from: "off",
            to: "on",
          },
          {
            platform: "state",
            entity_id: e.peakWindow,
            from: "off",
            to: "on",
          },
          { platform: "time_pattern", minutes: "/5" },
        ],
        variables: {
          alert_key: `{{ now().strftime('%Y-%m-%d') ~ ('-peak-am' if is_state('${e.peakWindow}', 'on') and now().hour < 12 else '-peak-pm' if is_state('${e.peakWindow}', 'on') else '-off-peak') }}`,
        },
        conditions: [
          { condition: "state", entity_id: e.batteryAtReserve, state: "on" },
          {
            condition: "template",
            value_template: `{{ states('${e.reserveAlertKey}') != alert_key }}`,
          },
        ],
        actions: notifyFamily(
          "Home Energy: battery at reserve",
          `The EG4 battery bank is at {{ states('${e.batterySoc}') }}% (reserve {{ states('${e.batteryReserve}') }}%). {% if is_state('${e.peakWindow}', 'on') %}SRP peak is active with {{ states('${e.peakMinutesRemaining}') }} minutes remaining; the battery may no longer supplement the home.{% else %}This occurred before the current SRP peak window.{% endif %}`,
          e.reserveAlertKey,
        ),
        mode: "single",
      },
    },
    {
      id: "home_energy_peak_battery_forecast_alert",
      config: {
        alias: "Home Energy — battery may not last through peak",
        description: "Alerts when the conservative 15-minute discharge forecast reaches the 20% reserve before the active SRP peak window ends.",
        triggers: [
          {
            platform: "state",
            entity_id: e.peakForecastShortfall,
            from: "off",
            to: "on",
            for: "00:02:00",
          },
          { platform: "time_pattern", minutes: "/5" },
        ],
        variables: {
          alert_key: "{{ now().strftime('%Y-%m-%d') ~ ('-am' if now().hour < 12 else '-pm') }}",
        },
        conditions: [
          { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
          { condition: "state", entity_id: e.peakWindow, state: "on" },
          { condition: "template", value_template: peakControlWindowTemplate(e) },
          { condition: "state", entity_id: e.peakForecastShortfall, state: "on" },
          {
            condition: "template",
            value_template: `{{ as_timestamp(now()) - as_timestamp(states['${e.peakForecastShortfall}'].last_changed, as_timestamp(now())) >= 120 }}`,
          },
          {
            condition: "template",
            value_template: `{{ states('${e.forecastAlertKey}') != alert_key }}`,
          },
        ],
        actions: notifyFamily(
          "Home Energy: battery shortfall forecast",
          `The conservative forecast reaches the {{ states('${e.batteryReserve}') }}% reserve in about {{ states('${e.batteryMinutesToReserve}') }} minutes, with {{ states('${e.peakMinutesRemaining}') }} peak minutes remaining. {% if is_state('${e.hvacResponseEnabled}', 'on') %}Peak Controls is enabled and can raise selected cooling setpoints after SOC reaches {{ states('${e.hvacSocGuardrail}') }}%, subject to its one-shot safety rules.{% else %}Peak Controls is disabled, so this is a dry-run alert; consider raising cooling setpoints within your comfort limit.{% endif %}`,
          e.forecastAlertKey,
        ),
        mode: "single",
      },
    },
    {
      id: "home_energy_live_peak_import_alert",
      config: {
        alias: "Home Energy — sustained peak grid import",
        description: "Alerts once when EG4's whole-property CT reports material import for five minutes during an SRP peak window.",
        triggers: [
          {
            platform: "state",
            entity_id: e.livePeakImportRisk,
            from: "off",
            to: "on",
            for: "00:05:00",
          },
          { platform: "time_pattern", minutes: "/5" },
        ],
        variables: {
          alert_key: "{{ now().strftime('%Y-%m-%d') ~ ('-am' if now().hour < 12 else '-pm') }}",
        },
        conditions: [
          { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
          { condition: "state", entity_id: e.peakWindow, state: "on" },
          { condition: "template", value_template: peakControlWindowTemplate(e) },
          { condition: "state", entity_id: e.livePeakImportRisk, state: "on" },
          {
            condition: "template",
            value_template: sustainedImportRiskTemplate(e),
          },
          {
            condition: "template",
            value_template: `{{ states('${e.peakImportAlertKey}') != alert_key }}`,
          },
        ],
        actions: notifyFamily(
          "Home Energy: sustained peak import",
          `Whole-property grid import has remained above {{ states('${e.peakImportThreshold}') }} kW for five minutes during the SRP peak window. Current import is {{ (states('${e.gridImportPower}') | float / 1000) | round(1) }} kW; sustained import can increase billed demand.`,
          e.peakImportAlertKey,
        ),
        mode: "single",
      },
    },
    {
      id: "home_energy_peak_hvac_response",
      config: {
        alias: "Home Energy — peak HVAC response",
        description: "Once per configured peak-control window, raises only selected cooling setpoints when forecast/SOC or sustained EG4 grid-import risk requires demand reduction.",
        triggers: [
          { platform: "time_pattern", minutes: "/1", seconds: "30" },
          {
            platform: "state",
            entity_id: [
              e.hvacResponseEnabled,
              e.peakScheduleValid,
              e.peakWindow,
              e.hvacWindowStart,
              e.hvacWindowEnd,
            ],
          },
        ],
        variables: {
          event_key: peakControlEventKeyTemplate(e),
          activation_reason: `{{ 'battery forecast shortfall at or below the SOC guardrail' if is_state('${e.peakForecastShortfall}', 'on') and is_number(states('${e.batterySoc}')) and is_number(states('${e.hvacSocGuardrail}')) and (states('${e.batterySoc}') | float) <= (states('${e.hvacSocGuardrail}') | float) else 'sustained whole-property grid import' }}`,
        },
        conditions: [],
        actions: [
          {
            choose: [
              {
                conditions: peakHvacActivationConditions(e, zones),
                sequence: peakHvacActivationSequence(e, zones),
              },
            ],
          },
        ],
        mode: "restart",
        max_exceeded: "silent",
      },
    },
    {
      id: "home_energy_peak_hvac_override_guard",
      config: {
        alias: "Home Energy — peak HVAC override guard",
        description: "Releases per-zone ownership when a person or another automation changes a controlled target or leaves cooling mode.",
        triggers: [
          {
            platform: "state",
            entity_id: zones.map((zone) => zone.climate),
          },
          { platform: "time_pattern", minutes: "/1", seconds: "40" },
        ],
        conditions: [
          { condition: "state", entity_id: e.hvacControllerActive, state: "on" },
        ],
        actions: [
          ...zones.map((zone) => overrideZoneAction(zone, e)),
          { delay: "00:00:01" },
          {
            choose: [
              {
                conditions: zones.map((zone) => ({
                  condition: "state",
                  entity_id: zone.owned,
                  state: "off",
                })),
                sequence: [
                  { action: "input_boolean.turn_off", target: { entity_id: e.hvacControllerActive } },
                  {
                    action: "input_text.set_value",
                    target: { entity_id: e.hvacControllerStatus },
                    data: { value: "Released — all selected zones were changed outside Peak Controls; no restoration will run." },
                  },
                ],
              },
            ],
          },
        ],
        mode: "queued",
        max: 10,
        max_exceeded: "silent",
      },
    },
    {
      id: "home_energy_peak_hvac_release",
      config: {
        alias: "Home Energy — release peak HVAC response",
        description: "Just before the configured end, or at actual peak end, master disable, or invalid schedule, restores only still-owned targets and yields to manual/scheduled changes.",
        triggers: [
          { platform: "time_pattern", minutes: "/1", seconds: "15" },
          { platform: "state", entity_id: e.hvacResponseEnabled, to: "off" },
          { platform: "state", entity_id: e.peakWindow, to: "off" },
          { platform: "state", entity_id: e.peakScheduleValid, to: "off" },
          { platform: "state", entity_id: [e.hvacWindowStart, e.hvacWindowEnd] },
        ],
        conditions: [
          { condition: "state", entity_id: e.hvacControllerActive, state: "on" },
          { condition: "or", conditions: [
            {
              condition: "template",
              value_template: `{{ not is_state('${e.hvacResponseEnabled}', 'on')
                or not is_state('${e.peakScheduleValid}', 'on')
                or not is_state('${e.peakWindow}', 'on') }}`,
            },
            { condition: "template", value_template: peakControlOutsideWindowTemplate(e) },
            { condition: "template", value_template: peakControlEndingSoonTemplate(e) },
          ] },
        ],
        actions: [
          {
            action: "input_text.set_value",
            target: { entity_id: e.hvacControllerStatus },
            data: { value: "Releasing — waiting for any in-flight thermostat call to settle." },
          },
          { delay: "00:00:10" },
          { action: "input_boolean.turn_off", target: { entity_id: e.hvacControllerActive } },
          ...zones.map((zone) => releaseZoneAction(zone, e)),
          ...zones.map(clearZoneOwnershipAction),
          {
            action: "input_text.set_value",
            target: { entity_id: e.hvacControllerStatus },
            data: { value: "Released — restored only zones still at the controller-applied target; external changes were preserved." },
          },
          {
            action: "persistent_notification.create",
            data: {
              title: "Home Energy: A/C demand response released",
              notification_id: "home_energy_peak_hvac_response",
              message: "Peak Controls released thermostat ownership. Restoration was attempted only for enabled zones that still exactly matched the controller-applied target; manual and scheduled changes were preserved.",
            },
          },
          {
            action: "script.notify_family",
            continue_on_error: true,
            data: {
              title: "Home Energy: A/C demand response released",
              message: "Peak Controls released thermostat ownership and preserved any manual or scheduled target changes.",
            },
          },
        ],
        mode: "single",
        max_exceeded: "silent",
      },
    },
  ];
}
