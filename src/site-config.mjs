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
]);

const notifyFamily = (title, message) => [
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
        ],
        conditions: [
          { condition: "state", entity_id: e.batteryAtReserve, state: "on" },
        ],
        actions: notifyFamily(
          "Home Energy: battery at reserve",
          `The EG4 battery bank is at {{ states('${e.batterySoc}') }}% (reserve {{ states('${e.batteryReserve}') }}%). {% if is_state('${e.peakWindow}', 'on') %}SRP peak is active with {{ states('${e.peakMinutesRemaining}') }} minutes remaining; the battery may no longer supplement the home.{% else %}This occurred before the current SRP peak window.{% endif %}`,
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
        ],
        conditions: [
          { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
          { condition: "state", entity_id: e.peakWindow, state: "on" },
        ],
        actions: notifyFamily(
          "Home Energy: battery shortfall forecast",
          `The conservative forecast reaches the {{ states('${e.batteryReserve}') }}% reserve in about {{ states('${e.batteryMinutesToReserve}') }} minutes, with {{ states('${e.peakMinutesRemaining}') }} peak minutes remaining. Consider raising cooling setpoints within your comfort limit to reduce A/C demand. Automatic thermostat changes are not armed.`,
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
        ],
        conditions: [
          { condition: "state", entity_id: e.peakScheduleValid, state: "on" },
          { condition: "state", entity_id: e.peakWindow, state: "on" },
        ],
        actions: notifyFamily(
          "Home Energy: sustained peak import",
          `Whole-property grid import has remained above {{ states('${e.peakImportThreshold}') }} kW for five minutes during the SRP peak window. Current import is {{ (states('${e.gridImportPower}') | float / 1000) | round(1) }} kW; sustained import can increase billed demand.`,
        ),
        mode: "single",
      },
    },
  ];
}
