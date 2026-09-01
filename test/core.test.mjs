import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  checkHomeAssistantConfig,
  restartHomeAssistant,
} from "../scripts/control-home-assistant.mjs";
import { waitForHomeAssistant } from "../scripts/wait-for-home-assistant.mjs";
import { buildDashboard, dashboardMetadata } from "../src/dashboard.mjs";
import {
  applyDashboard,
  applyHelpers,
  collectEntityReferences,
  stableString,
  validateAutomationTemplates,
  validateDashboard,
} from "../src/deployer.mjs";
import { discoverHomeEnergy, discoveryContract } from "../src/discovery.mjs";
import {
  evaluatePeakControl,
  isTimeInWindow,
  parseTimeMinutes,
  peakControlDefaults,
  planZoneAdjustment,
  planZoneRestoration,
} from "../src/peak-controls.mjs";
import { buildAutomations, helperSpecifications } from "../src/site-config.mjs";

function slug(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function fixture() {
  const registry = [];
  const states = [];
  for (const [key, [domain, originalName]] of Object.entries(discoveryContract.calculated)) {
    const entityId = `${domain}.home_energy_${slug(originalName)}`;
    registry.push({ entity_id: entityId, platform: "home_energy_monitor", original_name: originalName, disabled_by: null });
    states.push({ entity_id: entityId, state: key.includes("Problem") ? "off" : "1", attributes: {} });
  }
  for (const [key, [platform, domain, originalName]] of Object.entries(discoveryContract.sources)) {
    const entityId = `${domain}.${platform}_${slug(originalName)}`;
    registry.push({ entity_id: entityId, platform, original_name: originalName, disabled_by: null });
    states.push({ entity_id: entityId, state: key.includes("Lifetime") ? "100" : "1000", attributes: {} });
  }
  for (const entityId of Object.values(discoveryContract.static)) {
    states.push({ entity_id: entityId, state: "off", attributes: {} });
  }
  return { entities: registry, states };
}

test("semantic discovery resolves every calculated, source, and site entity", () => {
  const discovered = discoverHomeEnergy(fixture());
  assert.equal(Object.keys(discovered.entities).length, 81);
  assert.equal(discovered.entities.peakWindow, "input_boolean.juicebox_srp_on_peak");
  assert.match(discovered.entities.combinedSolarPower, /^sensor\./);
});

test("semantic discovery refuses ambiguous model entities", () => {
  const data = fixture();
  const first = data.entities.find((entry) => entry.original_name === "Combined solar power");
  data.entities.push({ ...first, entity_id: "sensor.duplicate_combined_solar" });
  data.states.push({ entity_id: "sensor.duplicate_combined_solar", state: "1", attributes: {} });
  assert.throws(() => discoverHomeEnergy(data), /found 2/);
});

test("dashboard is native, responsive, guarded, and complete", () => {
  const data = fixture();
  const discovered = discoverHomeEnergy(data);
  const dashboard = buildDashboard(discovered);
  const result = validateDashboard(dashboard, data.states);
  assert.equal(dashboardMetadata.urlPath, "home-energy");
  assert.deepEqual(dashboard.views.map((view) => view.path), [
    "whole-home",
    "solar-arrays",
    "battery-backup",
    "grid-srp",
    "peak-strategy",
    "peak-controls",
    "diagnostics",
  ]);
  assert.ok(result.cardCount > 80);
  assert.ok(result.references.length >= 65);
  assert.equal(stableString(dashboard).includes("custom:"), false);
  assert.equal(stableString(dashboard).includes("climate.set_temperature"), false);
});

test("dashboard validation rejects missing entities and write actions", () => {
  const data = fixture();
  const dashboard = buildDashboard(discoverHomeEnergy(data));
  const references = collectEntityReferences(dashboard);
  const missing = [...references][0];
  assert.throws(
    () => validateDashboard(dashboard, data.states.filter((state) => state.entity_id !== missing)),
    /missing entities/,
  );
  dashboard.views[0].sections[0].cards.push({ type: "tile", entity: missing, tap_action: { action: "perform-action" } });
  assert.throws(() => validateDashboard(dashboard, data.states), /write\/navigation action/);
});

test("alert and HVAC automations are windowed, one-shot, and mode safe", () => {
  const automations = buildAutomations(discoverHomeEnergy(fixture()).entities);
  assert.deepEqual(automations.map((automation) => automation.id), [
    "home_energy_battery_reserve_alert",
    "home_energy_peak_battery_forecast_alert",
    "home_energy_live_peak_import_alert",
    "home_energy_peak_hvac_response",
    "home_energy_peak_hvac_override_guard",
    "home_energy_peak_hvac_release",
  ]);
  const serialized = stableString(automations);
  assert.match(serialized, /script.notify_family/);
  assert.match(serialized, /00:05:00/);
  assert.match(serialized, /input_text.set_value/);
  assert.match(serialized, /time_pattern/);
  assert.match(serialized, /climate\.set_temperature/);
  assert.match(serialized, /home_energy_hvac_response_enabled/);
  assert.match(serialized, /home_energy_hvac_controller_event_key/);
  assert.doesNotMatch(serialized, /climate\.set_hvac_mode/);
  assert.doesNotMatch(serialized, /climate\.turn_off/);
});

test("every automation template is rendered with its runtime variables before deployment", async () => {
  const automations = buildAutomations(discoverHomeEnergy(fixture()).entities);
  const calls = [];
  const client = {
    async request(path, options) {
      calls.push({ path, options });
      return "ok";
    },
  };
  const result = await validateAutomationTemplates(client, automations);
  assert.ok(result.templateCount >= 30);
  assert.equal(calls.length, result.templateCount);
  assert.ok(calls.every((call) => call.path === "/api/template"));
  assert.ok(calls.every((call) => call.options.body.variables.event_key));
  assert.ok(calls.some((call) => call.options.body.template.includes("activation_reason")));
});

test("peak-control time windows are start-inclusive, end-exclusive, and fail closed", () => {
  assert.equal(parseTimeMinutes("18:00:00"), 1080);
  assert.equal(parseTimeMinutes("24:00:00"), null);
  assert.equal(parseTimeMinutes("unavailable"), null);
  assert.equal(isTimeInWindow("18:00:00", "18:00:00", "20:00:00"), true);
  assert.equal(isTimeInWindow("19:59:59", "18:00:00", "20:00:00"), true);
  assert.equal(isTimeInWindow("20:00:00", "18:00:00", "20:00:00"), false);
  assert.equal(isTimeInWindow("23:30:00", "22:00:00", "02:00:00"), true);
  assert.equal(isTimeInWindow("01:59:00", "22:00:00", "02:00:00"), true);
  assert.equal(isTimeInWindow("02:00:00", "22:00:00", "02:00:00"), false);
  assert.equal(isTimeInWindow("18:00:00", "18:00:00", "18:00:00"), false);
});

test("peak-control risk requires every safety gate and latches one event", () => {
  const safe = {
    masterEnabled: true,
    scheduleValid: true,
    onPeak: true,
    inWindow: true,
    forecastShortfall: true,
    batterySoc: 25,
    socGuardrail: 25,
    importRisk: false,
    currentEventKey: "2026-08-31-18:00-20:00",
    lastEventKey: "",
  };
  assert.deepEqual(evaluatePeakControl(safe), { activate: true, reason: "forecast_shortfall" });
  assert.equal(evaluatePeakControl({ ...safe, batterySoc: 25.1 }).activate, false);
  assert.deepEqual(
    evaluatePeakControl({ ...safe, forecastShortfall: false, importRisk: true, batterySoc: "unavailable" }),
    { activate: true, reason: "sustained_grid_import" },
  );
  for (const change of [
    { masterEnabled: false },
    { scheduleValid: false },
    { onPeak: false },
    { inWindow: false },
    { lastEventKey: safe.currentEventKey },
  ]) assert.equal(evaluatePeakControl({ ...safe, ...change }).activate, false);
});

test("zone plans raise cooling only within caps and preserve external overrides", () => {
  assert.equal(peakControlDefaults.setpointIncreaseF, 2);
  assert.deepEqual(planZoneAdjustment({
    enabled: true,
    available: true,
    hvacMode: "cool",
    currentSetpoint: 76,
    increaseF: 2,
    zoneMaximumF: 80,
    climateMaximumF: 99,
  }), { apply: true, reason: "eligible", original: 76, target: 78 });
  assert.equal(planZoneAdjustment({
    enabled: true,
    available: true,
    hvacMode: "heat",
    currentSetpoint: 76,
    increaseF: 2,
    zoneMaximumF: 80,
    climateMaximumF: 99,
  }).apply, false);
  assert.equal(planZoneAdjustment({
    enabled: true,
    available: true,
    hvacMode: "cool",
    currentSetpoint: 79,
    increaseF: 2,
    zoneMaximumF: 80,
    climateMaximumF: 99,
  }).target, 80);
  assert.deepEqual(planZoneRestoration({
    restorationEnabled: true,
    owned: true,
    currentSetpoint: 78,
    appliedSetpoint: 78,
    originalSetpoint: 76,
  }), { restore: true, reason: "still_owned", target: 76 });
  assert.equal(planZoneRestoration({
    restorationEnabled: true,
    owned: true,
    currentSetpoint: 77,
    appliedSetpoint: 78,
    originalSetpoint: 76,
  }).reason, "externally_overridden");
});

class HelperSocket {
  constructor({ failAfter = Infinity } = {}) {
    this.items = new Map();
    this.calls = [];
    this.failAfter = failAfter;
  }

  async call(command) {
    this.calls.push(command);
    if (this.calls.length === this.failAfter) throw new Error("injected failure");
    const [domain, action] = command.type.split("/");
    if (action === "list") return [...(this.items.get(domain)?.values() ?? [])];
    const idKey = `${domain}_id`;
    if (action === "create") {
      const id = slug(command.name);
      const item = { id, ...command };
      delete item.type;
      if (domain !== "input_text") delete item.initial;
      if (!this.items.has(domain)) this.items.set(domain, new Map());
      this.items.get(domain).set(id, item);
      return item;
    }
    if (action === "update") {
      const item = { id: command[idKey], ...command };
      delete item.type;
      delete item[idKey];
      this.items.get(domain).set(item.id, item);
      return item;
    }
    if (action === "delete") {
      this.items.get(domain)?.delete(command[idKey]);
      return null;
    }
    throw new Error(`Unexpected command ${command.type}`);
  }
}

test("helper deployment is idempotent", async () => {
  const latches = helperSpecifications.filter((helper) => helper.domain === "input_text");
  assert.equal(latches.length, 5);
  assert.equal(latches.some((helper) => "initial" in helper.config), false);
  const socket = new HelperSocket();
  const first = await applyHelpers(socket, helperSpecifications);
  assert.equal(first.changes.length, 31);
  const second = await applyHelpers(socket, helperSpecifications);
  assert.equal(second.changes.length, 0);
  const masterCreate = socket.calls.find((call) => call.type === "input_boolean/create"
    && call.name === "Home Energy HVAC Response Enabled");
  assert.equal(masterCreate.initial, false);
  assert.equal("initial" in socket.items.get("input_boolean").get("home_energy_hvac_response_enabled"), false);
});

test("helper metadata updates never reset persisted control values", async () => {
  const socket = new HelperSocket();
  await applyHelpers(socket, helperSpecifications);
  const stored = socket.items.get("input_number").get("home_energy_hvac_soc_guardrail_percent");
  stored.icon = "mdi:alert";
  const updated = await applyHelpers(socket, helperSpecifications);
  assert.equal(updated.changes.length, 1);
  const updateCall = socket.calls.findLast((call) => call.type === "input_number/update");
  assert.equal(updateCall.input_number_id, "home_energy_hvac_soc_guardrail_percent");
  assert.equal("initial" in updateCall, false);
});

test("helper deployment removes restart-resetting initial values from alert latches", async () => {
  const socket = new HelperSocket();
  const legacy = helperSpecifications.map((helper) => (
    helper.domain === "input_text"
      ? { ...helper, config: { ...helper.config, initial: "none" } }
      : helper
  ));
  await applyHelpers(socket, legacy);
  const migrated = await applyHelpers(socket, helperSpecifications);
  assert.equal(migrated.changes.length, 5);
  for (const latch of helperSpecifications.filter((helper) => helper.domain === "input_text")) {
    assert.equal("initial" in socket.items.get("input_text").get(latch.id), false);
  }
});

test("dashboard create rollback deletes only the dashboard it created", async () => {
  const calls = [];
  const ws = {
    async call(command) {
      calls.push(command);
      if (command.type === "lovelace/dashboards/create") return { id: "home_energy" };
      return null;
    },
  };
  const result = await applyDashboard({
    ws,
    existing: null,
    existingConfig: null,
    candidate: { views: [{ title: "Whole Home", path: "whole-home", cards: [] }] },
    metadata: dashboardMetadata,
  });
  await result.rollback();
  assert.deepEqual(calls.map((call) => call.type), [
    "lovelace/dashboards/create",
    "lovelace/config/save",
    "lovelace/dashboards/delete",
  ]);
});

test("restart health distinguishes first install from a loaded config-entry upgrade", async () => {
  let entries = [];
  const fetchImpl = async (url) => {
    const path = new URL(url).pathname;
    const value = path === "/api/config" ? { version: "2026.8.3" } : entries;
    return new Response(JSON.stringify(value), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const options = {
    baseUrl: "http://home-assistant.test",
    token: "test-token",
    timeoutMs: 20,
    retryDelayMs: 0,
    entryDomain: "home_energy_monitor",
    fetchImpl,
  };

  const firstInstall = await waitForHomeAssistant({ ...options, allowMissingEntry: true });
  assert.equal(firstInstall.entryStatus, "absent");

  await assert.rejects(
    waitForHomeAssistant({ ...options, allowMissingEntry: false }),
    /required home_energy_monitor config entry is missing/,
  );

  entries = [{ domain: "home_energy_monitor", state: "setup_error" }];
  await assert.rejects(
    waitForHomeAssistant({ ...options, allowMissingEntry: false }),
    /config entry is setup_error, not loaded/,
  );

  entries = [{ domain: "home_energy_monitor", state: "loaded" }];
  const upgrade = await waitForHomeAssistant({ ...options, allowMissingEntry: false });
  assert.equal(upgrade.entryStatus, "loaded");
});

test("authenticated control validates Home Assistant configuration", async () => {
  const calls = [];
  const options = {
    baseUrl: "http://home-assistant.test",
    token: "test-token",
    fetchImpl: async (url, request) => {
      calls.push({ url, request });
      return new Response(JSON.stringify({ result: "valid", errors: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  };
  await checkHomeAssistantConfig(options);
  assert.equal(new URL(calls[0].url).pathname, "/api/config/core/check_config");
  assert.equal(calls[0].request.method, "POST");
  assert.equal(calls[0].request.headers.Authorization, "Bearer test-token");

  await assert.rejects(
    checkHomeAssistantConfig({
      ...options,
      fetchImpl: async () => new Response(
        JSON.stringify({ result: "invalid", errors: "bad config" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    }),
    /bad config/,
  );
});

test("authenticated control requests a Home Assistant restart", async () => {
  const calls = [];
  const client = {
    async connect() {
      calls.push("connect");
    },
    async call(command) {
      calls.push(command);
      return null;
    },
    close() {
      calls.push("close");
    },
  };
  await restartHomeAssistant({
    baseUrl: "http://home-assistant.test/",
    token: "test-token",
    client,
  });
  assert.deepEqual(calls, [
    "connect",
    {
      type: "call_service",
      domain: "homeassistant",
      service: "restart",
      service_data: {},
      target: {},
    },
    "close",
  ]);
});

test("installer keeps deployment artifacts outside custom_components", () => {
  for (const path of [
    "../scripts/install-integration.mjs",
    "../scripts/install-integration-privileged.sh",
  ]) {
    const installer = readFileSync(new URL(path, import.meta.url), "utf8");
    assert.match(installer, /\/config\/\.home_energy_monitor_deployments/);
    assert.doesNotMatch(installer, /\/config\/custom_components\/\.home_energy_monitor/);
  }
});
