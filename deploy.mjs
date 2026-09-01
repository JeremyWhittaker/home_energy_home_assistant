#!/usr/bin/env node

import { buildDashboard, dashboardMetadata } from "./src/dashboard.mjs";
import {
  applyAutomations,
  applyDashboard,
  applyHelpers,
  createBackup,
  planDashboard,
  stableString,
  validateAutomationTemplates,
  validateDashboard,
  validateDashboardTemplates,
  verifyDashboard,
} from "./src/deployer.mjs";
import { discoverHomeEnergy } from "./src/discovery.mjs";
import { HomeAssistantClient } from "./src/ha-client.mjs";
import { buildAutomations, helperSpecifications } from "./src/site-config.mjs";

const DOMAIN = "home_energy_monitor";

function pause(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function parseArguments(argv) {
  const result = { check: false };
  for (const value of argv) {
    if (value === "--check") result.check = true;
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node deploy.mjs [--check]");
      process.exit(0);
    } else throw new Error(`Unknown argument: ${value}`);
  }
  return result;
}

async function ensureIntegration(client, checkOnly, transaction) {
  let entries = await client.call({ type: "config_entries/get" });
  let matches = entries.filter((entry) => entry.domain === DOMAIN);
  if (matches.length > 1) throw new Error(`Expected at most one ${DOMAIN} config entry; found ${matches.length}`);
  if (!matches.length) {
    if (checkOnly) throw new Error(`${DOMAIN} is not configured; run the deployer without --check`);
    const initial = await client.request("/api/config/config_entries/flow", {
      method: "POST",
      body: {
        handler: DOMAIN,
        show_advanced_options: false,
      },
    });
    if (initial.type !== "form") throw new Error(`Unexpected config-flow result: ${initial.type}`);
    const result = await client.request(`/api/config/config_entries/flow/${initial.flow_id}`, {
      method: "POST",
      body: {
        battery_capacity_kwh: 28,
        battery_reserve_percent: 20,
        peak_import_threshold_kw: 5,
        planning_discharge_kw: 7,
        minimum_discharge_kw: 0.3,
      },
    });
    if (result.type !== "create_entry") throw new Error(`Config flow did not create an entry: ${result.type}`);
    transaction.createdIntegrationEntryId = result.result?.entry_id ?? null;
    entries = await client.call({ type: "config_entries/get" });
    matches = entries.filter((entry) => entry.domain === DOMAIN);
    if (matches.length === 1 && !transaction.createdIntegrationEntryId) {
      transaction.createdIntegrationEntryId = matches[0].entry_id;
    }
  }
  if (matches.length !== 1) throw new Error(`Could not resolve the ${DOMAIN} config entry`);
  if (!new Set(["loaded", "setup_retry"]).has(matches[0].state)) {
    throw new Error(`${DOMAIN} config entry is ${matches[0].state}`);
  }
  return matches[0];
}

async function getLiveModel(client, timeoutMs = 90_000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    const [states, entities] = await Promise.all([
      client.request("/api/states"),
      client.call({ type: "config/entity_registry/list" }),
    ]);
    try {
      return { states, entities, discovery: discoverHomeEnergy({ entities, states }) };
    } catch (error) {
      lastError = error;
    }
    await pause(1_000);
  }
  throw new Error(`Calculated entities did not become ready: ${lastError?.message ?? "timeout"}`);
}

async function helperPrior(ws) {
  const lists = new Map();
  for (const { domain } of helperSpecifications) {
    if (!lists.has(domain)) lists.set(domain, await ws.call({ type: `${domain}/list` }));
  }
  return helperSpecifications.map((specification) => ({
    domain: specification.domain,
    id: specification.id,
    config: lists.get(specification.domain).find((item) => item.id === specification.id) ?? null,
  }));
}

async function automationPrior(client, automations) {
  return Promise.all(automations.map(async (automation) => ({
    id: automation.id,
    config: await client.request(`/api/config/automation/config/${automation.id}`, { allowNotFound: true }),
  })));
}

async function verifyHelpers(ws) {
  for (const specification of helperSpecifications) {
    const items = await ws.call({ type: `${specification.domain}/list` });
    if (!items.some((item) => item.id === specification.id)) {
      throw new Error(`Helper did not round-trip: ${specification.domain}.${specification.id}`);
    }
  }
}

async function verifyAutomations(client, automations) {
  for (const automation of automations) {
    const current = await client.request(`/api/config/automation/config/${automation.id}`);
    const { id: _id, ...withoutId } = current;
    if (stableString(withoutId) !== stableString(automation.config)) {
      throw new Error(`Automation did not round-trip: ${automation.id}`);
    }
  }
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  const client = new HomeAssistantClient({
    baseUrl: process.env.HA_BASE_URL,
    token: process.env.HA_TOKEN,
    timeoutMs: Number(process.env.HA_TIMEOUT_MS ?? 20_000),
  });
  await client.connect();
  let helperResult;
  let automationResult;
  let dashboardResult;
  const transaction = { createdIntegrationEntryId: null };
  try {
    const user = await client.call({ type: "auth/current_user" });
    if (!user?.is_admin) throw new Error("The Home Assistant token must belong to an administrator");
    const config = await client.request("/api/config");
    const entry = await ensureIntegration(client, args.check, transaction);
    const live = await getLiveModel(client);
    const candidate = buildDashboard(live.discovery);
    const automations = buildAutomations(live.discovery.entities);
    const dashboards = await client.call({ type: "lovelace/dashboards/list" });
    const existing = dashboards.find((dashboard) => dashboard.url_path === dashboardMetadata.urlPath) ?? null;
    const existingConfig = existing?.mode === "storage"
      ? await client.call({ type: "lovelace/config", url_path: dashboardMetadata.urlPath, force: true })
      : null;
    const plan = planDashboard({ existing, existingConfig, candidate, metadata: dashboardMetadata });

    if (args.check) {
      const validation = validateDashboard(candidate, live.states);
      const dashboardTemplates = await validateDashboardTemplates(client, candidate);
      const automationTemplates = await validateAutomationTemplates(client, automations);
      await verifyHelpers(client);
      await verifyAutomations(client, automations);
      await verifyDashboard({ ws: client, metadata: dashboardMetadata, candidate });
      console.log(`check-ok ha=${config.version} entry=${entry.state} dashboard=${plan.action} views=${validation.viewCount} cards=${validation.cardCount} entities=${validation.references.length} dashboard_templates=${dashboardTemplates.templateCount} automation_templates=${automationTemplates.templateCount}`);
      return;
    }

    const prior = {
      dashboard: existing ? { metadata: existing, config: existingConfig } : null,
      helpers: await helperPrior(client),
      automations: await automationPrior(client, automations),
    };
    const { path: backupPath } = createBackup({
      baseUrl: client.baseUrl,
      haVersion: config.version ?? client.version,
      metadata: dashboardMetadata,
      prior,
      candidate,
      helpers: helperSpecifications,
      automations,
    });
    console.log(`backup=${backupPath}`);

    helperResult = await applyHelpers(client, helperSpecifications);
    const refreshed = await getLiveModel(client);
    const validation = validateDashboard(candidate, refreshed.states);
    const dashboardTemplates = await validateDashboardTemplates(client, candidate);
    const automationTemplates = await validateAutomationTemplates(client, automations);
    const services = await client.request("/api/services");
    const scriptServices = services.find((service) => service.domain === "script")?.services ?? {};
    if (!("notify_family" in scriptServices)) throw new Error("Required script.notify_family service is unavailable");
    automationResult = await applyAutomations(client, automations);
    dashboardResult = await applyDashboard({
      ws: client,
      existing,
      existingConfig,
      candidate,
      metadata: dashboardMetadata,
    });
    await verifyHelpers(client);
    await verifyAutomations(client, automations);
    await verifyDashboard({ ws: client, metadata: dashboardMetadata, candidate });
    console.log(`deployment-ok ha=${config.version} entry=${entry.state} dashboard=${dashboardResult.action} views=${validation.viewCount} cards=${validation.cardCount} entities=${validation.references.length} dashboard_templates=${dashboardTemplates.templateCount} automation_templates=${automationTemplates.templateCount} helpers=${helperResult.changes.length} automations=${automationResult.changes.length}`);
  } catch (error) {
    const rollbackErrors = [];
    for (const result of [dashboardResult, automationResult, helperResult]) {
      if (!result?.rollback) continue;
      try {
        await result.rollback();
      } catch (rollbackError) {
        rollbackErrors.push(rollbackError.message);
      }
    }
    if (transaction.createdIntegrationEntryId) {
      try {
        await client.request(
          `/api/config/config_entries/entry/${encodeURIComponent(transaction.createdIntegrationEntryId)}`,
          { method: "DELETE" },
        );
      } catch (rollbackError) {
        rollbackErrors.push(`config entry: ${rollbackError.message}`);
      }
    }
    if (rollbackErrors.length) {
      throw new Error(`${error.message}; rollback failures: ${rollbackErrors.join("; ")}`, { cause: error });
    }
    throw new Error(`${error.message}; site-configuration rollback completed`, { cause: error });
  } finally {
    client.close();
  }
}

main().catch((error) => {
  console.error(`ERROR: ${error.message}`);
  process.exitCode = 1;
});
