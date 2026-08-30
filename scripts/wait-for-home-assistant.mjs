#!/usr/bin/env node

const baseUrl = String(process.env.HA_BASE_URL ?? "").replace(/\/$/, "");
const token = process.env.HA_TOKEN;
const timeoutMs = Number(process.env.HA_HEALTH_TIMEOUT_MS ?? 180_000);
const initialDelayMs = Number(process.env.HA_HEALTH_INITIAL_DELAY_MS ?? 0);

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function main() {
  if (!baseUrl) throw new Error("Set HA_BASE_URL to the Home Assistant URL");
  if (!token) throw new Error("Set HA_TOKEN to a Home Assistant administrator token");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error("HA_HEALTH_TIMEOUT_MS must be a positive number");
  }
  if (!Number.isFinite(initialDelayMs) || initialDelayMs < 0) {
    throw new Error("HA_HEALTH_INITIAL_DELAY_MS must be zero or a positive number");
  }

  const deadline = Date.now() + timeoutMs;
  let lastError;
  if (initialDelayMs) await delay(initialDelayMs);

  while (Date.now() < deadline) {
    try {
      const remaining = Math.max(250, deadline - Date.now());
      const response = await fetch(`${baseUrl}/api/config`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(Math.min(5_000, remaining)),
      });
      if (response.ok) {
        const config = await response.json();
        if (!config || typeof config.version !== "string") {
          throw new Error("authenticated /api/config response did not contain a version");
        }
        console.log(`ha-health-ok version=${config.version}`);
        return;
      }
      lastError = new Error(`authenticated /api/config returned HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await delay(Math.min(2_000, Math.max(0, deadline - Date.now())));
  }

  throw new Error(
    `Home Assistant did not become healthy within ${timeoutMs} ms: ${lastError?.message ?? "timeout"}`,
  );
}

main().catch((error) => {
  console.error(`ERROR: ${error.message}`);
  process.exitCode = 1;
});
