const ENTITY_ID_PATTERN = /^[a-z_]+\.[a-z0-9_]+$/;

const CALCULATED = Object.freeze({
  combinedSolarPower: ["sensor", "Combined solar power"],
  combinedAcSupplyPower: ["sensor", "Combined AC supply power"],
  wholeHomeLoad: ["sensor", "Whole home load estimate"],
  eg4MeteredLoad: ["sensor", "EG4 vendor-calculated load power"],
  gridNetPower: ["sensor", "Grid net power"],
  gridImportPower: ["sensor", "Grid import power"],
  gridExportPower: ["sensor", "Grid export power"],
  batteryNetPower: ["sensor", "Battery net power"],
  batterySoc: ["sensor", "Battery SOC"],
  batteryAvailableEnergy: ["sensor", "Battery energy above reserve"],
  batteryDischargeAverage: ["sensor", "Battery discharge average 15m"],
  batteryDischargeP80: ["sensor", "Battery discharge p80 15m"],
  batteryMinutesToReserve: ["sensor", "Battery minutes to reserve"],
  batteryReserveEta: ["sensor", "Battery reserve ETA"],
  combinedSolarEnergy: ["sensor", "Combined solar energy"],
  peakMinutesRemaining: ["sensor", "Peak minutes remaining"],
  peakStrategyStatus: ["sensor", "Peak strategy status"],
  sourceHealth: ["sensor", "Source health"],
  tigoArrayPower: ["sensor", "Tigo diagnostic array power"],
  tigoAlignedEg4Power: ["sensor", "Tigo sample aligned EG4 power"],
  tigoRatio: ["sensor", "Tigo to EG4 ratio"],
  enphaseActiveMicroinverters: ["sensor", "Enphase active microinverters"],
  srpSettledNetEnergy: ["sensor", "SRP settled net energy"],
  eg4SameDayNetEnergy: ["sensor", "EG4 same day net energy"],
  gridReconciliationResidual: ["sensor", "Grid reconciliation residual"],
  gridReconciliationDate: ["sensor", "Grid reconciliation date"],
  srpCurrentDemand: ["sensor", "SRP current cycle demand"],
  srpBilledCyclePeak: ["sensor", "SRP billed cycle peak"],
  srpBillProjection: ["sensor", "SRP bill projection"],
  measurementModelValid: ["binary_sensor", "Measurement model valid"],
  telemetryHealthy: ["binary_sensor", "Telemetry healthy"],
  tigoModuleProblem: ["binary_sensor", "Tigo module problem"],
  enphaseSystemProblem: ["binary_sensor", "Enphase system problem"],
  srpIntegrationAvailable: ["binary_sensor", "SRP integration available"],
  batteryAtReserve: ["binary_sensor", "Battery at reserve"],
  peakForecastShortfall: ["binary_sensor", "Peak forecast shortfall"],
  livePeakImportRisk: ["binary_sensor", "Live peak import risk"],
  gridReconciliationMatches: ["binary_sensor", "Grid reconciliation matches"],
});

const SOURCES = Object.freeze({
  eg4PvPower: ["eg4_web_monitor", "sensor", "PV Total Power"],
  eg4YieldLifetime: ["eg4_web_monitor", "sensor", "Yield (Lifetime)"],
  eg4GridImportLifetime: ["eg4_web_monitor", "sensor", "Grid Import (Lifetime)"],
  eg4GridExportLifetime: ["eg4_web_monitor", "sensor", "Grid Export (Lifetime)"],
  enphasePower: ["enphase_envoy", "sensor", "Current power production"],
  enphaseLifetime: ["enphase_envoy", "sensor", "Lifetime energy production"],
});

const STATIC = Object.freeze({
  peakWindow: "input_boolean.juicebox_srp_on_peak",
  peakScheduleValid: "input_boolean.juicebox_srp_schedule_valid",
  peakProfile: "input_text.juicebox_srp_profile_name",
  batteryCapacity: "input_number.home_energy_battery_capacity_kwh",
  batteryReserve: "input_number.home_energy_battery_reserve_percent",
  peakImportThreshold: "input_number.home_energy_peak_import_threshold_kw",
  planningDischarge: "input_number.home_energy_planning_discharge_kw",
  reserveAlertKey: "input_text.home_energy_reserve_alert_key",
  forecastAlertKey: "input_text.home_energy_forecast_alert_key",
  peakImportAlertKey: "input_text.home_energy_peak_import_alert_key",
  downstairsClimate: "climate.east_ac_down",
  primaryClimate: "climate.west_ac_down",
  upstairsClimate: "climate.upstairs_ac",
});

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

function liveIds(states) {
  return new Set(states.map((state) => state.entity_id));
}

function resolve(registry, available, { platform, domain, originalName, key }) {
  const matches = registry.filter((entry) =>
    entry.platform === platform
    && entry.disabled_by == null
    && entry.entity_id?.startsWith(`${domain}.`)
    && normalize(entry.original_name) === normalize(originalName)
  );
  if (matches.length !== 1) {
    const detail = matches.map((entry) => entry.entity_id).join(", ") || "none";
    throw new Error(`Expected one enabled ${platform} ${originalName} entity for ${key}; found ${matches.length}: ${detail}`);
  }
  const entityId = matches[0].entity_id;
  if (!ENTITY_ID_PATTERN.test(entityId) || !available.has(entityId)) {
    throw new Error(`Discovered ${key} is not a valid live entity: ${entityId}`);
  }
  return entityId;
}

export function discoverHomeEnergy({ entities, states }) {
  if (!Array.isArray(entities) || !Array.isArray(states)) {
    throw new TypeError("entities and states must be arrays");
  }
  const available = liveIds(states);
  const calculated = Object.fromEntries(Object.entries(CALCULATED).map(([key, [domain, originalName]]) => [
    key,
    resolve(entities, available, {
      platform: "home_energy_monitor",
      domain,
      originalName,
      key,
    }),
  ]));
  const sources = Object.fromEntries(Object.entries(SOURCES).map(([key, [platform, domain, originalName]]) => [
    key,
    resolve(entities, available, { platform, domain, originalName, key }),
  ]));
  return Object.freeze({
    entities: Object.freeze({ ...calculated, ...sources, ...STATIC }),
  });
}

export const discoveryContract = Object.freeze({ calculated: CALCULATED, sources: SOURCES, static: STATIC });
