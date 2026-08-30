#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { accessSync, constants } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { waitForHomeAssistant } from "./wait-for-home-assistant.mjs";

const repository = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(repository, "custom_components/home_energy_monitor");
const host = process.env.HA_SSH_HOST ?? "homeassistant-ha";
const target = "/config/custom_components/home_energy_monitor";
const nonce = `${Date.now()}-${process.pid}`;
const staging = `/config/custom_components/.home_energy_monitor.staging-${nonce}`;
const backup = `/config/custom_components/.home_energy_monitor.backup-${nonce}`;
const failed = `/config/custom_components/.home_energy_monitor.failed-${nonce}`;

function run(command, args, { allowFailure = false, quiet = false } = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: quiet ? ["ignore", "pipe", "pipe"] : ["ignore", "inherit", "inherit"],
    timeout: 180_000,
  });
  if (result.error) throw result.error;
  if (result.status !== 0 && !allowFailure) {
    const detail = quiet ? `: ${(result.stderr || result.stdout).trim()}` : "";
    throw new Error(`${command} exited ${result.status}${detail}`);
  }
  return result;
}

function remoteExists(path) {
  return run("ssh", [host, "test", "-d", path], { allowFailure: true, quiet: true }).status === 0;
}

async function main() {
  accessSync(source, constants.R_OK);
  const preflight = await waitForHomeAssistant({
    timeoutMs: 15_000,
    entryDomain: "home_energy_monitor",
    allowMissingEntry: true,
  });
  const entryHealthRequired = preflight.entryStatus === "loaded";
  const verifyPostRestart = () => waitForHomeAssistant({
    timeoutMs: 180_000,
    initialDelayMs: 10_000,
    entryDomain: entryHealthRequired ? "home_energy_monitor" : "",
    allowMissingEntry: false,
  });
  const hadPrior = remoteExists(target);
  let activated = false;
  try {
    run("ssh", [host, "mkdir", staging]);
    run("rsync", [
      "-a",
      "--exclude",
      "__pycache__",
      "--exclude",
      "*.pyc",
      `${source}/`,
      `${host}:${staging}/`,
    ]);
    if (hadPrior) run("ssh", [host, "mv", target, backup]);
    run("ssh", [host, "mv", staging, target]);
    activated = true;
    run("ssh", [host, "ha", "core", "check"]);
    run("ssh", [host, "ha", "core", "restart"]);
    const health = await verifyPostRestart();
    console.log(`integration-install-ok ha=${health.version} component=${target} prior=${hadPrior ? backup : "none"}`);
  } catch (error) {
    const rollbackErrors = [];
    try {
      if (activated && remoteExists(target)) run("ssh", [host, "mv", target, failed]);
      else if (remoteExists(staging)) run("ssh", [host, "mv", staging, failed]);
      if (hadPrior && remoteExists(backup)) run("ssh", [host, "mv", backup, target]);
      if (activated) {
        run("ssh", [host, "ha", "core", "restart"]);
        await verifyPostRestart();
      }
    } catch (rollbackError) {
      rollbackErrors.push(rollbackError.message);
    }
    const suffix = rollbackErrors.length
      ? `; rollback failures: ${rollbackErrors.join("; ")}`
      : `; component rollback completed (failed copy retained at ${failed})`;
    throw new Error(`${error.message}${suffix}`, { cause: error });
  }
}

main().catch((error) => {
  console.error(`ERROR: ${error.message}`);
  process.exitCode = 1;
});
