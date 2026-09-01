export const peakControlDefaults = Object.freeze({
  windowStart: "18:00:00",
  windowEnd: "20:00:00",
  socGuardrailPercent: 25,
  setpointIncreaseF: 2,
  zoneMaximumF: 80,
});

export function parseTimeMinutes(value) {
  if (typeof value !== "string") return null;
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(value.trim());
  if (!match) return null;
  const [, hourText, minuteText, secondText = "0"] = match;
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  if (hour > 23 || minute > 59 || second > 59) return null;
  return hour * 60 + minute + second / 60;
}

export function isTimeInWindow(current, start, end) {
  const currentMinutes = typeof current === "number" ? current : parseTimeMinutes(current);
  const startMinutes = typeof start === "number" ? start : parseTimeMinutes(start);
  const endMinutes = typeof end === "number" ? end : parseTimeMinutes(end);
  if (![currentMinutes, startMinutes, endMinutes].every(Number.isFinite)) return false;
  if (startMinutes === endMinutes) return false;
  return startMinutes < endMinutes
    ? currentMinutes >= startMinutes && currentMinutes < endMinutes
    : currentMinutes >= startMinutes || currentMinutes < endMinutes;
}

export function secondsUntilWindowEnd(current, start, end) {
  const currentMinutes = typeof current === "number" ? current : parseTimeMinutes(current);
  const startMinutes = typeof start === "number" ? start : parseTimeMinutes(start);
  const endMinutes = typeof end === "number" ? end : parseTimeMinutes(end);
  if (![currentMinutes, startMinutes, endMinutes].every(Number.isFinite)) return null;
  if (!isTimeInWindow(currentMinutes, startMinutes, endMinutes)) return null;
  const remainingMinutes = endMinutes > currentMinutes
    ? endMinutes - currentMinutes
    : (24 * 60) - currentMinutes + endMinutes;
  return remainingMinutes * 60;
}

export function evaluatePeakControl({
  masterEnabled,
  scheduleValid,
  onPeak,
  inWindow,
  forecastShortfall,
  batterySoc,
  socGuardrail,
  importRisk,
  currentEventKey,
  lastEventKey,
}) {
  if (!masterEnabled) return { activate: false, reason: "disabled" };
  if (!scheduleValid) return { activate: false, reason: "schedule_invalid" };
  if (!onPeak) return { activate: false, reason: "off_peak" };
  if (!inWindow) return { activate: false, reason: "outside_window" };
  if (!currentEventKey || currentEventKey === lastEventKey) {
    return { activate: false, reason: "already_handled" };
  }
  const soc = Number(batterySoc);
  const guardrail = Number(socGuardrail);
  const forecastRisk = Boolean(forecastShortfall)
    && Number.isFinite(soc)
    && Number.isFinite(guardrail)
    && soc <= guardrail;
  if (forecastRisk) return { activate: true, reason: "forecast_shortfall" };
  if (importRisk) return { activate: true, reason: "sustained_grid_import" };
  return { activate: false, reason: "no_risk" };
}

export function planZoneAdjustment({
  enabled,
  available,
  hvacMode,
  currentSetpoint,
  increaseF,
  zoneMaximumF,
  climateMaximumF,
}) {
  if (!enabled) return { apply: false, reason: "zone_disabled" };
  if (!available) return { apply: false, reason: "unavailable" };
  if (hvacMode !== "cool") return { apply: false, reason: "not_cooling" };
  const values = [currentSetpoint, increaseF, zoneMaximumF, climateMaximumF].map(Number);
  if (!values.every(Number.isFinite)) return { apply: false, reason: "invalid_temperature" };
  const [current, increase, zoneMaximum, climateMaximum] = values;
  if (increase <= 0) return { apply: false, reason: "invalid_increase" };
  const target = Math.min(current + increase, zoneMaximum, climateMaximum);
  if (target <= current) return { apply: false, reason: "at_comfort_cap" };
  return { apply: true, reason: "eligible", original: current, target };
}

export function planZoneRestoration({
  restorationEnabled,
  owned,
  currentSetpoint,
  appliedSetpoint,
  originalSetpoint,
  toleranceF = 0.1,
}) {
  if (!restorationEnabled) return { restore: false, reason: "restoration_disabled" };
  if (!owned) return { restore: false, reason: "not_owned" };
  const values = [currentSetpoint, appliedSetpoint, originalSetpoint, toleranceF].map(Number);
  if (!values.every(Number.isFinite)) return { restore: false, reason: "invalid_temperature" };
  const [current, applied, original, tolerance] = values;
  if (Math.abs(current - applied) > Math.max(tolerance, 0)) {
    return { restore: false, reason: "externally_overridden" };
  }
  return { restore: true, reason: "still_owned", target: original };
}
