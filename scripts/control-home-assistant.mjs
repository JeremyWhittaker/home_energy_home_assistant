#!/usr/bin/env node

import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

function settings(options = {}) {
  const baseUrl = String(options.baseUrl ?? process.env.HA_BASE_URL ?? "").replace(/\/$/, "");
  const token = options.token ?? process.env.HA_TOKEN;
  const timeoutMs = Number(options.timeoutMs ?? 20_000);
  if (!baseUrl) throw new Error("Set HA_BASE_URL to the Home Assistant URL");
  if (!token) throw new Error("Set HA_TOKEN to a Home Assistant administrator token");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error("timeoutMs must be positive");
  return { baseUrl, token, timeoutMs, fetchImpl: options.fetchImpl ?? fetch };
}

async function post(path, options = {}) {
  const { baseUrl, token, timeoutMs, fetchImpl } = settings(options);
  const response = await fetchImpl(baseUrl + path, {
    method: "POST",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    body: "{}",
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`POST ${path} returned HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  return text ? JSON.parse(text) : null;
}

export async function checkHomeAssistantConfig(options = {}) {
  const result = await post("/api/config/core/check_config", options);
  if (result?.result !== "valid" || result.errors) {
    throw new Error(
      "Home Assistant configuration is invalid: "
        + (result?.errors ?? JSON.stringify(result)),
    );
  }
  return result;
}

export async function restartHomeAssistant(options = {}) {
  await post("/api/services/homeassistant/restart", options);
}

async function main() {
  const action = process.argv[2];
  if (action === "check") {
    await checkHomeAssistantConfig();
    console.log("ha-config-ok");
    return;
  }
  if (action === "restart") {
    await restartHomeAssistant();
    console.log("ha-restart-requested");
    return;
  }
  throw new Error("Usage: control-home-assistant.mjs check|restart");
}

const directPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : null;
if (directPath === import.meta.url) {
  main().catch((error) => {
    console.error("ERROR: " + error.message);
    process.exitCode = 1;
  });
}
