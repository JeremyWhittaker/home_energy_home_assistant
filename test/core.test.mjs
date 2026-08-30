import assert from "node:assert/strict";
import test from "node:test";

import { buildDashboard, dashboardMetadata } from "../src/dashboard.mjs";
import {
  applyDashboard,
  applyHelpers,
  collectEntityReferences,
  stableString,
  validateDashboard,
} from "../src/deployer.mjs";
import { discoverHomeEnergy, discoveryContract } from "../src/discovery.mjs";
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
  assert.equal(Object.keys(discovered.entities).length, 54);
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

test("dashboard is native, responsive, monitoring-only, and complete", () => {
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
    "diagnostics",
  ]);
  assert.ok(result.cardCount > 60);
  assert.ok(result.references.length > 40);
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

test("alert automations cover reserve, forecast, and sustained peak import without HVAC mutation", () => {
  const automations = buildAutomations(discoverHomeEnergy(fixture()).entities);
  assert.deepEqual(automations.map((automation) => automation.id), [
    "home_energy_battery_reserve_alert",
    "home_energy_peak_battery_forecast_alert",
    "home_energy_live_peak_import_alert",
  ]);
  const serialized = stableString(automations);
  assert.match(serialized, /script.notify_family/);
  assert.match(serialized, /00:05:00/);
  assert.doesNotMatch(serialized, /climate\.set_temperature/);
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
  const socket = new HelperSocket();
  const first = await applyHelpers(socket, helperSpecifications);
  assert.equal(first.changes.length, 4);
  const second = await applyHelpers(socket, helperSpecifications);
  assert.equal(second.changes.length, 0);
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
