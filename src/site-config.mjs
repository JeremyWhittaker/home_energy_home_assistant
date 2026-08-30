export const helperSpecifications = Object.freeze([
  {
    domain: "input_number",
    id: "home_energy_battery_capacity_kwh",
    config: {
      name: "Home Energy Battery Capacity kWh",
      icon: "mdi:battery-high",
      min: 1,
      max: 100,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kWh",
      initial: 28,
    },
  },
  {
    domain: "input_number",
    id: "home_energy_battery_reserve_percent",
    config: {
      name: "Home Energy Battery Reserve Percent",
      icon: "mdi:battery-alert-variant-outline",
      min: 0,
      max: 50,
      step: 1,
      mode: "box",
      unit_of_measurement: "%",
      initial: 20,
    },
  },
  {
    domain: "input_number",
    id: "home_energy_peak_import_threshold_kw",
    config: {
      name: "Home Energy Peak Import Threshold kW",
      icon: "mdi:transmission-tower-import",
      min: 0.5,
      max: 25,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kW",
      initial: 5,
    },
  },
  {
    domain: "input_number",
    id: "home_energy_planning_discharge_kw",
    config: {
      name: "Home Energy Planning Discharge kW",
      icon: "mdi:battery-clock-outline",
      min: 0.5,
      max: 25,
      step: 0.5,
      mode: "box",
      unit_of_measurement: "kW",
      initial: 7,
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

export function buildAutomations(e) {
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
          `The conservative forecast reaches the {{ states('${e.batteryReserve}') }}% reserve in about {{ states('${e.batteryMinutesToReserve}') }} minutes, with {{ states('${e.peakMinutesRemaining}') }} peak minutes remaining. Consider raising cooling setpoints within your comfort limit to reduce A/C demand. Automatic thermostat changes are not armed.`,
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
          { condition: "state", entity_id: e.livePeakImportRisk, state: "on" },
          {
            condition: "template",
            value_template: `{{ as_timestamp(now()) - as_timestamp(states['${e.livePeakImportRisk}'].last_changed, as_timestamp(now())) >= 300 }}`,
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
  ];
}
