#!/usr/bin/env node

import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function environmentBoolean(name) {
  return new Set(["1", "true", "yes"]).has(String(process.env[name] ?? "").toLowerCase());
}

export async function waitForHomeAssistant(options = {}) {
  const baseUrl = String(options.baseUrl ?? process.env.HA_BASE_URL ?? "");
  const normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const token = options.token ?? process.env.HA_TOKEN;
  const timeoutMs = Number(options.timeoutMs ?? process.env.HA_HEALTH_TIMEOUT_MS ?? 180_000);
  const initialDelayMs = Number(
    options.initialDelayMs ?? process.env.HA_HEALTH_INITIAL_DELAY_MS ?? 0,
  );
  const retryDelayMs = Number(
    options.retryDelayMs ?? process.env.HA_HEALTH_RETRY_DELAY_MS ?? 2_000,
  );
  const entryDomain = String(
    options.entryDomain ?? process.env.HA_HEALTH_ENTRY_DOMAIN ?? "",
  ).trim();
  const allowMissingEntry = options.allowMissingEntry
    ?? environmentBoolean("HA_HEALTH_ALLOW_MISSING_ENTRY");
  const fetchImpl = options.fetchImpl ?? fetch;

  if (!normalizedBaseUrl) throw new Error("Set HA_BASE_URL to the Home Assistant URL");
  if (!token) throw new Error("Set HA_TOKEN to a Home Assistant administrator token");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error("HA_HEALTH_TIMEOUT_MS must be a positive number");
  }
  if (!Number.isFinite(initialDelayMs) || initialDelayMs < 0) {
    throw new Error("HA_HEALTH_INITIAL_DELAY_MS must be zero or a positive number");
  }
  if (!Number.isFinite(retryDelayMs) || retryDelayMs < 0) {
    throw new Error("HA_HEALTH_RETRY_DELAY_MS must be zero or a positive number");
  }

  const deadline = Date.now() + timeoutMs;
  let lastError;
  if (initialDelayMs) await delay(initialDelayMs);

  while (Date.now() < deadline) {
    try {
      const remaining = Math.max(250, deadline - Date.now());
      const request = async (path) => {
        const response = await fetchImpl(normalizedBaseUrl + path, {
          headers: { Authorization: "Bearer " + token },
          signal: AbortSignal.timeout(Math.min(5_000, remaining)),
        });
        if (!response.ok) {
          throw new Error("authenticated " + path + " returned HTTP " + response.status);
        }
        return response.json();
      };
      const config = await request("/api/config");
      if (!config || typeof config.version !== "string") {
        throw new Error("authenticated /api/config response did not contain a version");
      }

      let entryStatus = null;
      if (entryDomain) {
        const entries = await request(
          "/api/config/config_entries/entry?domain=" + encodeURIComponent(entryDomain),
        );
        if (!Array.isArray(entries)) {
          throw new Error("config-entry health response was not an array");
        }
        if (entries.length > 1) {
          throw new Error(
            "expected at most one " + entryDomain + " config entry; found " + entries.length,
          );
        }
        if (entries.length === 0) {
          if (!allowMissingEntry) {
            throw new Error("required " + entryDomain + " config entry is missing");
          }
          entryStatus = "absent";
        } else {
          entryStatus = String(entries[0].state ?? "unknown");
          if (entryStatus !== "loaded") {
            throw new Error(
              entryDomain + " config entry is " + entryStatus + ", not loaded",
            );
          }
        }
      }

      return { version: config.version, entryStatus };
    } catch (error) {
      lastError = error;
    }
    await delay(Math.min(retryDelayMs, Math.max(0, deadline - Date.now())));
  }

  throw new Error(
    "Home Assistant did not become healthy within "
      + timeoutMs
      + " ms: "
      + (lastError?.message ?? "timeout"),
  );
}

async function main() {
  const result = await waitForHomeAssistant();
  const entry = result.entryStatus ? " entry=" + result.entryStatus : "";
  console.log("ha-health-ok version=" + result.version + entry);
}

const directPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : null;
if (directPath === import.meta.url) {
  main().catch((error) => {
    console.error("ERROR: " + error.message);
    process.exitCode = 1;
  });
}
