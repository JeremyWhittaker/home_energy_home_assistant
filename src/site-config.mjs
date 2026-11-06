import { peakControlDefaults } from "./peak-controls.mjs";

const FAMILY_PRESENCE = "group.family_presence";

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
  ...["dispatch_failure", "eg4_unusable", "controller_fault", "profile_mismatch"].map((kind) => ({
    domain: "input_text",
    id: `home_energy_${kind}_alert_key`,
    config: {
      name: `Home Energy ${kind.replaceAll("_", " ")} Alert Key`,
      icon: "mdi:message-badge-outline", min: 0, max: 128, mode: "text",
    },
  })),
  ...["day", "key", "local_key"].map((kind) => ({
    domain: "input_text", id: `home_energy_demand_review_${kind}`,
    config: { name: `Home Energy demand review ${kind.replaceAll("_", " ")}`,
      icon: "mdi:email-check-outline", min: 0, max: 128, mode: "text" },
  })),
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

const JEREMY_EMAIL_ACCOUNT = "notify.email_notification_sender_1";

export function jeremyEmailAvailableTemplate(e) {
  return `{{ state_attr('${e.sourceHealth}', 'jeremy_email_available') == true
    and states['${JEREMY_EMAIL_ACCOUNT}'] is not none
    and not is_state('${JEREMY_EMAIL_ACCOUNT}', 'unavailable') }}`;
}

function emailAction(title, message) {
  return { action: "email_notifier.send", continue_on_error: true,
    data: { account: JEREMY_EMAIL_ACCOUNT, title, message } };
}

function jeremyEmailOrLocal(e, title, message, notificationId) {
  return { choose: [{ conditions: [{ condition: "template", value_template: jeremyEmailAvailableTemplate(e) }],
    sequence: [emailAction(title, message)],
  }], default: [{ action: "persistent_notification.create", data: {
    title: "Home Energy: Jeremy email unavailable", notification_id: notificationId,
    message: "The configured email action/account is unavailable. The energy notice remains in Home Assistant; no email delivery is claimed.",
  } }] };
}

export function currentEnergyContext(e) {
  return `Reported snapshot at {{ now().strftime('%b %-d, %-I:%M %p %Z') }}.
Grid import: {{ states('${e.gridImportPower}') }} W.
Battery: {{ states('${e.batteryNetPower}') }} W (positive discharge, negative charge), SOC {{ states('${e.batterySoc}') }}%.
Inverter controller: {{ states('sensor.home_energy_inverter_schedule_status') }}; profile {{ state_attr('sensor.home_energy_inverter_schedule_status', 'profile') or 'unverified' }}.
Orange EVSE: {{ states('sensor.openevse_evse_state') }}; Grey EVSE: {{ states('sensor.juicebox_status') }}.
Downstairs: {{ states('${e.downstairsClimate}') }}, {{ state_attr('${e.downstairsClimate}', 'hvac_action') or 'unknown action' }}.
Primary: {{ states('${e.primaryClimate}') }}, {{ state_attr('${e.primaryClimate}', 'hvac_action') or 'unknown action' }}.
Upstairs: {{ states('${e.upstairsClimate}') }}, {{ state_attr('${e.upstairsClimate}', 'hvac_action') or 'unknown action' }}.
These are current reported states, not proof of an appliance's contribution, delivered EV energy or billed demand cost.`;
}

function notifyFamilyAndJeremyEmail(e, title, message, latch) {
  const original = notifyFamily(title, message, latch);
  return [...original.slice(0, -1), original.at(-1),
    jeremyEmailOrLocal(e, title, `${message}\n\n${currentEnergyContext(e)}`, "home_energy_peak_email_unavailable")];
}

export function demandReviewTemplates(e) {
  const id = e.srpDemandAudit;
  const prefix = `{% set checked = as_timestamp(state_attr('${id}', 'last_checked'), none) %}
{% set age = as_timestamp(now()) - checked if checked is number else -1 %}
{% set day = state_attr('${id}', 'latest_complete_day') %}
{% set parsed = as_datetime(day, none) %}
{% set day_age = (now().date() - parsed.date()).days if parsed is not none else -1 %}
{% set demand = state_attr('${id}', 'latest_daily_max_kw') %}
{% set threshold = states('${e.peakImportThreshold}') %}
{% set status = states('${id}') %}
{% set material_key = day ~ '|' ~ status ~ '|' ~ (demand | round(1) if demand is number else 'unknown') %}`;
  const usable = `age is number and 0 <= age <= 21600 and 1 <= day_age <= 2
    and state_attr('${id}', 'content_hash') is string
    and (state_attr('${id}', 'content_hash') | length) > 0`;
  return {
    email: `${prefix}
{{ ${usable} and now().hour >= 10
    and (status == 'mismatch' or (status == 'matches' and demand is number
      and is_number(threshold) and demand >= threshold | float))
    and states('input_text.home_energy_demand_review_day') != now().strftime('%Y-%m-%d')
    and states('input_text.home_energy_demand_review_key') != material_key }}`,
    local: `${prefix}
{{ not (${usable}) or status in ['incomplete', 'unsupported', 'unknown', 'unavailable'] }}`,
    key: `${prefix}{{ material_key }}`,
    localKey: `{{ now().strftime('%Y-%m-%d') ~ '|' ~ states('${id}') ~ '|'
      ~ (state_attr('${id}', 'latest_complete_day') or 'none') }}`,
    message: `SRP demand audit: {{ states('${id}') }}. Latest complete day: {{ state_attr('${id}', 'latest_complete_day') or 'unavailable' }}.
Reported daily on-peak maximum: {{ state_attr('${id}', 'latest_daily_max_kw') }} kW.
{% set events = state_attr('${id}', 'latest_complete_day_winning_intervals') or [] %}
{% for item in events[:3] %}Winning half-hour: {{ item['start'] }} to {{ item['end'] }}, {{ item['demand_kw'] }} kW.\n{% endfor %}
This checks utility interval demand against its daily summary; a derived cycle average is not independent bill verification. Demand-charge dollars remain unverified; the projected total bill is not the demand-charge line.
Current HA states do not identify which appliance caused an earlier utility event. Review coincident history and control faults before changing habits; avoid overlapping discretionary loads during verified peak hours when practical.
Recent utility days may be revised. Source caveats: {{ state_attr('${id}', 'caveats') or 'See SRP demand audit details.' }}`,
  };
}

function buildDemandReview(e) {
  const t = demandReviewTemplates(e);
  const set = (kind, value) => ({ action: "input_text.set_value",
    target: { entity_id: `input_text.home_energy_demand_review_${kind}` }, data: { value } });
  return { id: "home_energy_srp_demand_review", config: {
    alias: "Home Energy: daily SRP demand review",
    description: "At most one meaningful Jeremy email attempt per day; only recent completed utility days, never invented billing dollars.",
    triggers: [{ platform: "state", entity_id: e.srpDemandAudit },
      { platform: "time", at: "10:00:00" }, { platform: "time_pattern", minutes: "15" },
      { platform: "homeassistant", event: "start" }],
    variables: { review_key: t.key, local_key: t.localKey },
    conditions: [],
    actions: [{ choose: [
      { conditions: [{ condition: "template", value_template: t.email }], sequence: [
        { choose: [{ conditions: [{ condition: "template", value_template: jeremyEmailAvailableTemplate(e) }], sequence: [
          // Persist attempt intent before the service to bound restart/timeout duplicates.
          set("day", "{{ now().strftime('%Y-%m-%d') }}"),
          set("key", "{{ review_key | default('unavailable') }}"),
          emailAction("Home Energy: SRP demand review", t.message),
          { action: "persistent_notification.create", data: {
            title: "Home Energy: demand review email requested", notification_id: "home_energy_demand_review",
            message: `${t.message}\nEmail was requested through the existing Jeremy account; inbox delivery is not independently confirmed.`,
          } },
        ] }], default: [{ action: "persistent_notification.create", data: {
          title: "Home Energy: demand review email unavailable", notification_id: "home_energy_demand_email_unavailable",
          message: "The configured Jeremy email action/account is unavailable. Demand findings remain local; no email attempt or delivery is claimed.",
        } }] },
      ] },
      { conditions: [{ condition: "template", value_template: t.local },
          { condition: "template", value_template: "{{ states('input_text.home_energy_demand_review_local_key') != local_key | default('unavailable') }}" }], sequence: [
        { action: "persistent_notification.create", data: {
          title: "Home Energy: SRP demand audit incomplete", notification_id: "home_energy_demand_review",
          message: `State: {{ states('${e.srpDemandAudit}') }}. A fresh complete demand audit is unavailable or unsupported. Missing intervals are not zero; no demand-cost conclusion or email is issued. {{ state_attr('${e.srpDemandAudit}', 'caveats') or '' }}`,
        } }, set("local_key", "{{ local_key | default('unavailable') }}"),
      ] },
    ] }], mode: "single",
  } };
}

function sharedPeakExpression(e) {
  return `is_state('${e.peakScheduleValid}', 'on')
    and is_state('${e.peakWindow}', 'on')
    and is_state('input_boolean.juicebox_srp_schedule_enabled', 'on')
    and is_state('automation.juicebox_apply_local_charge_policy', 'on')
    and evaluated is number and 0 <= age <= 180`;
}

function sharedScheduleAgeTemplate() {
  return `{% set evaluated = as_timestamp(state_attr('automation.juicebox_apply_local_charge_policy', 'last_triggered'), none) %}
{% set age = as_timestamp(now()) - evaluated if evaluated is number else -1 %}`;
}

function peakControlWindowTemplate(e) {
  return `${sharedScheduleAgeTemplate()}
{{ ${sharedPeakExpression(e)} }}`;
}

function peakControlOutsideWindowTemplate(e) {
  return `${sharedScheduleAgeTemplate()}
{{ not (${sharedPeakExpression(e)})
    or not is_number(states('${e.peakMinutesRemaining}')) }}`;
}

function peakControlEndingSoonTemplate(e) {
  return `{% set remaining = states('${e.peakMinutesRemaining}') %}
{% set seconds_left = (remaining | float(0)) * 60 %}
{{ is_number(remaining) and 0 < seconds_left <= 60 }}`;
}

function peakControlHasActionTimeTemplate(e) {
  return `{% set remaining = states('${e.peakMinutesRemaining}') %}
{% set seconds_left = (remaining | float(0)) * 60 %}
{{ is_number(remaining) and seconds_left > 60 }}`;
}

function peakControlEventKeyTemplate(_e) {
  // E-15 has separate morning/evening winter periods and one afternoon
  // summer period. This key survives automation reloads and HA restarts.
  return `{{ now().strftime('%Y-%m-%d') ~ ('-am' if now().hour < 12 else '-pm') }}`;
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
    { condition: "state", entity_id: FAMILY_PRESENCE, state: "home" },
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
    { condition: "state", entity_id: FAMILY_PRESENCE, state: "home" },
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

export function householdShortfallTemplate(e) {
  return `{% set central = state_attr('${e.batteryMinutesToReserve}', 'central_minutes') %}
{% set conservative = state_attr('${e.batteryMinutesToReserve}', 'conservative_minutes') %}
{% set remaining = states('${e.peakMinutesRemaining}') %}
{{ state_attr('${e.batteryMinutesToReserve}', 'forecast_valid') == true
   and central is number and conservative is number and is_number(remaining)
   and 0 <= central <= remaining | float and 0 <= conservative <= remaining | float }}`;
}

const CONTROLLER_STATUS = "sensor.home_energy_inverter_schedule_status";
// Separate from the existing5kW demand/HVAC threshold and7kW planning value.
export const dispatchFailureImportThresholdW = 500;

function criticalEg4UsableExpression(e) {
  return `is_number(states('${e.batteryNetPower}')) and is_number(states('${e.batterySoc}'))
    and is_number(states('${e.gridNetPower}'))
    and state_attr('${e.batteryNetPower}', 'unit_of_measurement') == 'W'
    and state_attr('${e.batterySoc}', 'unit_of_measurement') == '%'
    and state_attr('${e.gridNetPower}', 'unit_of_measurement') == 'W'
    and 0 <= states('${e.batterySoc}') | float <= 100
    and health_age is number and 0 <= health_age <= 180
    and ages is mapping
    and ages.get('EG4 battery') is number and 0 <= ages['EG4 battery'] <= 5
    and ages.get('EG4 battery SOC') is number and 0 <= ages['EG4 battery SOC'] <= 5
    and ages.get('EG4 grid CT') is number and 0 <= ages['EG4 grid CT'] <= 5`;
}

function failureSourceVariables(e) {
  return `${sharedScheduleAgeTemplate()}
{% set ages = state_attr('${e.sourceHealth}', 'source_ages_minutes') %}
{% set health = states['${e.sourceHealth}'] %}
{% set health_age = as_timestamp(now()) - as_timestamp(health.last_reported, none)
   if health is defined and health.last_reported is defined else none %}`;
}

export function peakDispatchFailureTemplate(e) {
  return `${failureSourceVariables(e)}
{{ ${sharedPeakExpression(e)} and (${criticalEg4UsableExpression(e)})
    and is_number(states('${e.wholeHomeLoad}')) and is_number(states('${e.combinedSolarPower}'))
    and state_attr('${e.wholeHomeLoad}', 'unit_of_measurement') == 'W'
    and state_attr('${e.combinedSolarPower}', 'unit_of_measurement') == 'W'
    and states('${e.batterySoc}') | float > 25
    and states('${e.wholeHomeLoad}') | float - states('${e.combinedSolarPower}') | float > 1000
    and states('${e.gridNetPower}') | float > ${dispatchFailureImportThresholdW}
    and states('${e.batteryNetPower}') | float <= 300 }}`;
}

export function peakEg4UnusableTemplate(e) {
  return `${failureSourceVariables(e)}
{{ ${sharedPeakExpression(e)} and not (${criticalEg4UsableExpression(e)}) }}`;
}

function persistentFailure(title, message, latch) {
  return [
    { action: "persistent_notification.create", data: {
      title, message, notification_id: `home_energy_${latch}`,
    } },
    { action: "input_text.set_value", target: { entity_id: `input_text.home_energy_${latch}_alert_key` },
      data: { value: "{{ alert_key }}" } },
  ];
}

export function buildFailureAlerts(e) {
  const windowKey = peakControlEventKeyTemplate(e);
  const timed = (id, title, template, message) => ({ id: `home_energy_${id}_alert`, config: {
    alias: title, description: "Persistent Home Assistant diagnostic only; no automatic device action.",
    triggers: [{ platform: "template", value_template: template, for: "00:10:00" }],
    variables: { alert_key: windowKey },
    conditions: [
      { condition: "template", value_template: template },
      { condition: "template", value_template: `{{ states('input_text.home_energy_${id}_alert_key') != alert_key }}` },
    ],
    actions: persistentFailure(title, message, id), mode: "single",
  } });
  const faultTemplate = `{% set status = states('${CONTROLLER_STATUS}') %}
{% set item = states['${CONTROLLER_STATUS}'] %}
{% set age = as_timestamp(now()) - as_timestamp(item.last_changed, as_timestamp(now())) %}
{{ status in ['Recovery required', 'Automatic retries stopped']
   or (status == 'Blocked' and age >= 1800) }}`;
  const expectedTemplate = `{% set season = state_attr('${CONTROLLER_STATUS}', 'season') %}
{% set kind = state_attr('${CONTROLLER_STATUS}', 'day_kind') %}
{{ 'summer-weekly' if season == 'summer' and kind in ['weekday', 'weekend']
   else season ~ '-' ~ kind if season in ['winter', 'summer'] and kind in ['weekday', 'weekend', 'holiday']
   else '' }}`;
  return [
    timed("dispatch_failure", "Home Energy: peak battery support missing",
      peakDispatchFailureTemplate(e),
      "For ten minutes during SRP peak, reported grid import exceeded 0.5 kW while load exceeded solar by 1 kW, SOC was above 25% and the battery was not discharging above 300 W. Check the inverter schedule and current readings; this does not diagnose the cause."),
    timed("eg4_unusable", "Home Energy: peak EG4 readings unavailable",
      peakEg4UnusableTemplate(e),
      "EG4 battery power, SOC or service-grid readings have been unavailable or stale for ten minutes during SRP peak. Battery dispatch cannot be verified. A recent HA report alone does not prove a fresh vendor measurement."),
    { id: "home_energy_controller_fault_alert", config: {
      alias: "Home Energy: inverter scheduling needs attention",
      description: "Immediate recovery/retry-stop diagnostic or Blocked for 30 minutes; once per continuous status incident.",
      triggers: [
        { platform: "state", entity_id: CONTROLLER_STATUS, to: "Recovery required" },
        { platform: "state", entity_id: CONTROLLER_STATUS, to: "Automatic retries stopped" },
        { platform: "state", entity_id: CONTROLLER_STATUS, to: "Blocked", for: "00:30:00" },
        { platform: "time_pattern", minutes: "/5" },
      ],
      variables: { alert_key: `{{ states('${CONTROLLER_STATUS}') ~ '-' ~ as_timestamp(states['${CONTROLLER_STATUS}'].last_changed, 0) | int }}` },
      conditions: [ { condition: "template", value_template: faultTemplate },
        { condition: "template", value_template: "{{ states('input_text.home_energy_controller_fault_alert_key') != alert_key }}" } ],
      actions: persistentFailure("Home Energy: inverter scheduling needs attention",
        `Status: {{ states('${CONTROLLER_STATUS}') }}. {{ state_attr('${CONTROLLER_STATUS}', 'error') or '' }} Automatic retries stopped: {{ state_attr('${CONTROLLER_STATUS}', 'retry_exhausted') == true }}. Review the retained inverter settings; automatic control does not prove current power flow.`, "controller_fault"),
      mode: "single",
    } },
    { id: "home_energy_profile_mismatch_alert", config: {
      alias: "Home Energy: check inverter profile before peak",
      description: "Read-only profile check at 04:30 and 16:30 using the controller calendar, including weekends/holidays.",
      triggers: [{ platform: "time", at: "04:30:00" }, { platform: "time", at: "16:30:00" }],
      variables: { alert_key: windowKey, expected_profile: expectedTemplate },
      conditions: [
        { condition: "template", value_template: `{{ expected_profile | default('') != ''
          and state_attr('${CONTROLLER_STATUS}', 'shared_tariff_validated') == true
          and state_attr('${CONTROLLER_STATUS}', 'profile') != expected_profile | default('') }}` },
        { condition: "template", value_template: "{{ states('input_text.home_energy_profile_mismatch_alert_key') != alert_key }}" },
      ],
      actions: persistentFailure("Home Energy: check inverter profile before peak",
        `Expected {{ expected_profile | default('unavailable') }}, last verified {{ state_attr('${CONTROLLER_STATUS}', 'profile') or 'none' }}. Check scheduling before the next peak. This is a saved-profile comparison, not a fresh settings readback.`, "profile_mismatch"),
      mode: "single",
    } },
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
          `The EG4 battery bank is at {{ states('${e.batterySoc}') }}% (reserve {{ states('${e.batteryReserve}') }}%). {% if is_state('${e.peakWindow}', 'on') %}SRP peak is active with {{ states('${e.peakMinutesRemaining}') }} minutes remaining; the battery may no longer supplement the home.{% elif is_state('${e.peakHolidaysOffPeak}', 'on') and is_state('${e.peakHoliday}', 'on') %}Today is an SRP-observed holiday, so there is no on-peak period at all today and no demand charge to protect. This is a note, not a risk.{% else %}SRP peak is not active right now.{% endif %}`,
          e.reserveAlertKey,
        ),
        mode: "single",
      },
    },
    {
      id: "home_energy_peak_battery_forecast_alert",
      config: {
        alias: "Home Energy — battery may not last through peak",
        description: "Alerts only when valid central and conservative forecasts both reach reserve before the active SRP peak ends; the conservative HVAC risk guard remains separate.",
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
          { condition: "template", value_template: householdShortfallTemplate(e) },
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
          `Both forecasts predict reaching the {{ states('${e.batteryReserve}') }}% reserve before peak ends: central {{ state_attr('${e.batteryMinutesToReserve}', 'central_minutes') | round(0) if state_attr('${e.batteryMinutesToReserve}', 'central_minutes') is number else 'unavailable' }} minutes, conservative {{ states('${e.batteryMinutesToReserve}') }} minutes, with {{ states('${e.peakMinutesRemaining}') }} peak minutes remaining. {% if is_state('${e.hvacResponseEnabled}', 'on') %}Peak Controls is enabled and can raise selected cooling setpoints after SOC reaches {{ states('${e.hvacSocGuardrail}') }}%, subject to its one-shot safety rules.{% else %}Peak Controls is disabled, so this is a dry-run alert; consider raising cooling setpoints within your comfort limit.{% endif %}`,
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
        actions: notifyFamilyAndJeremyEmail(
          e, "Home Energy: sustained peak import",
          `Whole-property grid import has remained above {{ states('${e.peakImportThreshold}') }} kW for five minutes during the SRP peak window. {% set import_power = states('${e.gridImportPower}') %}Current import is {% if is_number(import_power) %}{{ (import_power | float / 1000) | round(1) }} kW{% else %}unavailable{% endif %}; sustained import can increase billed demand.`,
          e.peakImportAlertKey,
        ),
        mode: "single",
      },
    },
    ...buildFailureAlerts(e),
    buildDemandReview(e),
    {
      id: "home_energy_peak_hvac_response",
      config: {
        alias: "Home Energy — peak HVAC response",
        description: "Once per active SRP peak window while family is home, raises selected cooling setpoints when forecast/SOC or sustained EG4 grid-import risk requires demand reduction.",
        triggers: [
          { platform: "time_pattern", minutes: "/1", seconds: "30" },
          {
            platform: "state",
            entity_id: [
              e.hvacResponseEnabled,
              e.peakScheduleValid,
              e.peakWindow,
              FAMILY_PRESENCE,
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
          {
            condition: "template",
            value_template: `{{ not states('${e.hvacControllerStatus}').startswith('Releasing') }}`,
          },
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
        description: "Before actual SRP peak end, on family departure, master disable, or invalid schedule, restores still-owned targets before signalling that the comfort scheduler may take over.",
        triggers: [
          { platform: "time_pattern", minutes: "/1", seconds: "15" },
          { platform: "state", entity_id: e.hvacResponseEnabled, to: "off" },
          { platform: "state", entity_id: e.peakWindow, to: "off" },
          { platform: "state", entity_id: e.peakScheduleValid, to: "off" },
          { platform: "state", entity_id: "input_boolean.juicebox_srp_schedule_enabled", to: "off" },
          { platform: "state", entity_id: "automation.juicebox_apply_local_charge_policy", to: "off" },
          { platform: "state", entity_id: FAMILY_PRESENCE },
        ],
        conditions: [
          { condition: "state", entity_id: e.hvacControllerActive, state: "on" },
          { condition: "or", conditions: [
            {
              condition: "template",
              value_template: `{{ not is_state('${e.hvacResponseEnabled}', 'on')
                or not is_state('${e.peakScheduleValid}', 'on')
                or not is_state('${e.peakWindow}', 'on')
                or not is_state('${FAMILY_PRESENCE}', 'home') }}`,
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
          ...zones.map((zone) => releaseZoneAction(zone, e)),
          ...zones.map(clearZoneOwnershipAction),
          { action: "input_boolean.turn_off", target: { entity_id: e.hvacControllerActive } },
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
