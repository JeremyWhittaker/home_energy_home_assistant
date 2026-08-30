import { createHash } from "node:crypto";
import { closeSync, mkdtempSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ALLOWED_TYPES = new Set([
  "sections",
  "grid",
  "heading",
  "markdown",
  "tile",
  "gauge",
  "history-graph",
  "statistics-graph",
  "distribution",
  "entities",
  "entity",
  "entity-filter",
]);
const ENTITY_REFERENCE_PATTERN = /\b[a-z_][a-z0-9_]*\.[a-z0-9_]+\b/g;
const WRITE_ACTIONS = new Set(["call-service", "perform-action", "toggle", "navigate"]);
const METADATA_FIELDS = ["title", "icon", "show_in_sidebar", "require_admin"];

export function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  }
  return value;
}

export function stableString(value) {
  return JSON.stringify(stableValue(value));
}

export function checksum(value) {
  return createHash("sha256").update(stableString(value)).digest("hex");
}

export function collectEntityReferences(value, references = new Set()) {
  if (typeof value === "string") {
    for (const match of value.matchAll(ENTITY_REFERENCE_PATTERN)) references.add(match[0]);
  } else if (Array.isArray(value)) {
    for (const child of value) collectEntityReferences(child, references);
  } else if (value && typeof value === "object") {
    for (const child of Object.values(value)) collectEntityReferences(child, references);
  }
  return references;
}

export function collectDashboardTemplates(value, templates = []) {
  if (typeof value === "string") {
    if (value.includes("{{") || value.includes("{%")) templates.push(value);
  } else if (Array.isArray(value)) {
    for (const child of value) collectDashboardTemplates(child, templates);
  } else if (value && typeof value === "object") {
    for (const child of Object.values(value)) collectDashboardTemplates(child, templates);
  }
  return templates;
}

export async function validateDashboardTemplates(client, config) {
  const templates = collectDashboardTemplates(config);
  for (const template of templates) {
    await client.request("/api/template", {
      method: "POST",
      body: { template },
      responseType: "text",
    });
  }
  return { templateCount: templates.length };
}

export function validateDashboard(config, states) {
  if (!config || !Array.isArray(config.views) || config.views.length === 0) {
    throw new Error("Dashboard must contain at least one view");
  }
  const paths = config.views.map((view) => view.path);
  if (paths.some((path) => typeof path !== "string" || !path)) throw new Error("Every view needs a path");
  if (new Set(paths).size !== paths.length) throw new Error("Dashboard view paths must be unique");
  const live = new Set(states.map((state) => state.entity_id));
  const references = collectEntityReferences(config);
  const missing = [...references].filter((entityId) => !live.has(entityId));
  if (missing.length) throw new Error(`Dashboard references missing entities: ${missing.join(", ")}`);

  let cardCount = 0;
  function inspect(value) {
    if (Array.isArray(value)) {
      for (const child of value) inspect(child);
      return;
    }
    if (!value || typeof value !== "object") return;
    if (typeof value.type === "string") {
      cardCount += 1;
      if (value.type.startsWith("custom:") || !ALLOWED_TYPES.has(value.type)) {
        throw new Error(`Dashboard uses unsupported card or layout type: ${value.type}`);
      }
    }
    if (typeof value.action === "string" && WRITE_ACTIONS.has(value.action)) {
      throw new Error(`Monitoring dashboard contains a write/navigation action: ${value.action}`);
    }
    for (const child of Object.values(value)) inspect(child);
  }
  inspect(config);
  return { references: [...references].sort(), cardCount, viewCount: config.views.length };
}

function metadataPayload(metadata) {
  return {
    title: metadata.title,
    icon: metadata.icon,
    show_in_sidebar: metadata.showInSidebar,
    require_admin: metadata.requireAdmin,
  };
}

function metadataMatches(current, desired) {
  const payload = metadataPayload(desired);
  return METADATA_FIELDS.every((field) => (current?.[field] ?? null) === (payload[field] ?? null));
}

export function planDashboard({ existing, existingConfig, candidate, metadata }) {
  if (existing && existing.mode !== "storage") {
    throw new Error(`Dashboard ${metadata.urlPath} exists in ${existing.mode} mode; refusing to replace it`);
  }
  if (!existing) return { action: "create", configChanged: true, metadataChanged: true };
  const configChanged = stableString(existingConfig) !== stableString(candidate);
  const metadataChanged = !metadataMatches(existing, metadata);
  return { action: configChanged || metadataChanged ? "update" : "unchanged", configChanged, metadataChanged };
}

async function restoreDashboard(ws, { createdId, existing, existingConfig }) {
  if (!existing) {
    if (createdId) await ws.call({ type: "lovelace/dashboards/delete", dashboard_id: createdId });
    return;
  }
  await ws.call({ type: "lovelace/config/save", url_path: existing.url_path, config: existingConfig });
  await ws.call({
    type: "lovelace/dashboards/update",
    dashboard_id: existing.id,
    title: existing.title,
    icon: existing.icon ?? null,
    show_in_sidebar: existing.show_in_sidebar,
    require_admin: existing.require_admin,
  });
}

export async function applyDashboard({ ws, existing, existingConfig, candidate, metadata }) {
  const plan = planDashboard({ existing, existingConfig, candidate, metadata });
  if (plan.action === "unchanged") return { ...plan, dashboardId: existing.id, rollback: async () => {} };
  let createdId = null;
  if (!existing) {
    const created = await ws.call({
      type: "lovelace/dashboards/create",
      url_path: metadata.urlPath,
      mode: "storage",
      ...metadataPayload(metadata),
    });
    createdId = created.id;
    try {
      await ws.call({ type: "lovelace/config/save", url_path: metadata.urlPath, config: candidate });
    } catch (error) {
      await restoreDashboard(ws, { createdId, existing, existingConfig });
      throw error;
    }
  } else {
    try {
      if (plan.configChanged) {
        await ws.call({ type: "lovelace/config/save", url_path: metadata.urlPath, config: candidate });
      }
      if (plan.metadataChanged) {
        await ws.call({
          type: "lovelace/dashboards/update",
          dashboard_id: existing.id,
          ...metadataPayload(metadata),
        });
      }
    } catch (error) {
      await restoreDashboard(ws, { createdId, existing, existingConfig });
      throw error;
    }
  }
  return {
    ...plan,
    dashboardId: createdId ?? existing.id,
    rollback: () => restoreDashboard(ws, { createdId, existing, existingConfig }),
  };
}

export async function verifyDashboard({ ws, metadata, candidate }) {
  const dashboards = await ws.call({ type: "lovelace/dashboards/list" });
  const current = dashboards.find((dashboard) => dashboard.url_path === metadata.urlPath);
  if (!current || current.mode !== "storage") throw new Error("Dashboard is not registered in storage mode");
  if (!metadataMatches(current, metadata)) throw new Error("Dashboard metadata did not round-trip exactly");
  const config = await ws.call({ type: "lovelace/config", url_path: metadata.urlPath, force: true });
  if (stableString(config) !== stableString(candidate)) throw new Error("Dashboard config did not round-trip exactly");
  return { dashboard: current, config };
}

function helperConfig(item) {
  const { id: _id, ...config } = item;
  return config;
}

function comparableHelper(config) {
  const { initial: _initial, ...comparable } = config;
  return comparable;
}

export async function applyHelpers(ws, specifications) {
  const changes = [];
  try {
    for (const specification of specifications) {
      const items = await ws.call({ type: `${specification.domain}/list` });
      const existing = items.find((item) => item.id === specification.id) ?? null;
      if (!existing) {
        const created = await ws.call({ type: `${specification.domain}/create`, ...specification.config });
        if (created.id !== specification.id) {
          await ws.call({ type: `${specification.domain}/delete`, [`${specification.domain}_id`]: created.id });
          throw new Error(`Helper name produced ${created.id}; expected ${specification.id}`);
        }
        changes.push({ specification, action: "create", prior: null });
      } else if (stableString(comparableHelper(helperConfig(existing))) !== stableString(comparableHelper(specification.config))) {
        await ws.call({
          type: `${specification.domain}/update`,
          [`${specification.domain}_id`]: specification.id,
          ...specification.config,
        });
        changes.push({ specification, action: "update", prior: helperConfig(existing) });
      }
    }
  } catch (error) {
    await rollbackHelpers(ws, changes);
    throw error;
  }
  return { changes, rollback: () => rollbackHelpers(ws, changes) };
}

async function rollbackHelpers(ws, changes) {
  for (const change of [...changes].reverse()) {
    const { domain, id } = change.specification;
    if (change.action === "create") {
      await ws.call({ type: `${domain}/delete`, [`${domain}_id`]: id });
    } else {
      await ws.call({ type: `${domain}/update`, [`${domain}_id`]: id, ...change.prior });
    }
  }
}

function withoutId(config) {
  if (!config) return null;
  const { id: _id, ...rest } = config;
  return rest;
}

export async function applyAutomations(client, specifications) {
  const changes = [];
  try {
    for (const specification of specifications) {
      const path = `/api/config/automation/config/${specification.id}`;
      const current = await client.request(path, { allowNotFound: true });
      if (stableString(withoutId(current)) === stableString(specification.config)) continue;
      await client.request(path, { method: "POST", body: specification.config });
      changes.push({ specification, prior: current });
    }
  } catch (error) {
    await rollbackAutomations(client, changes);
    throw error;
  }
  return { changes, rollback: () => rollbackAutomations(client, changes) };
}

async function rollbackAutomations(client, changes) {
  for (const change of [...changes].reverse()) {
    const path = `/api/config/automation/config/${change.specification.id}`;
    if (change.prior) await client.request(path, { method: "POST", body: withoutId(change.prior) });
    else await client.request(path, { method: "DELETE" });
  }
}

export function createBackup({ baseUrl, haVersion, metadata, prior, candidate, helpers, automations }) {
  const directory = mkdtempSync(join(tmpdir(), "home-energy-ha-"));
  const path = join(directory, "backup.json");
  const backup = {
    schema: "home-energy-ha-backup/1",
    created_at: new Date().toISOString(),
    home_assistant: { base_url: baseUrl, version: haVersion },
    dashboard_path: metadata.urlPath,
    prior,
    deployed: { metadata: metadataPayload(metadata), config: candidate, checksum: checksum(candidate) },
    helper_changes: helpers,
    automation_changes: automations,
  };
  const descriptor = openSync(path, "wx", 0o600);
  try {
    writeFileSync(descriptor, `${JSON.stringify(backup, null, 2)}\n`, "utf8");
  } finally {
    closeSync(descriptor);
  }
  return { path, backup };
}

export function loadBackup(path) {
  const backup = JSON.parse(readFileSync(path, "utf8"));
  if (backup.schema !== "home-energy-ha-backup/1" || !backup.deployed?.config) {
    throw new Error("Backup is not a home-energy-ha-backup/1 document");
  }
  if (checksum(backup.deployed.config) !== backup.deployed.checksum) throw new Error("Backup checksum is invalid");
  return backup;
}
