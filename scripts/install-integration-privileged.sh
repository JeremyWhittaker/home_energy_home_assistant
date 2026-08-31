#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$repo_dir/custom_components/home_energy_monitor"
ssh_host=${HA_SSH_HOST:-homeassistant-ha}
nonce=$(date +%s)
archive=$(mktemp "/tmp/home-energy-monitor-${nonce}-XXXXXX.tar.gz")
remote_archive="/tmp/home-energy-monitor-${nonce}.tar.gz"
health_check="$repo_dir/scripts/wait-for-home-assistant.mjs"
ha_control="$repo_dir/scripts/control-home-assistant.mjs"

cleanup() {
  rm -f -- "$archive"
}
trap cleanup EXIT

: "${HA_BASE_URL:?Set HA_BASE_URL before running the installer}"
: "${HA_TOKEN:?Set HA_TOKEN before running the installer}"

preflight_health=$(
  HA_HEALTH_TIMEOUT_MS=15000 \
    HA_HEALTH_INITIAL_DELAY_MS=0 \
    HA_HEALTH_ENTRY_DOMAIN=home_energy_monitor \
    HA_HEALTH_ALLOW_MISSING_ENTRY=1 \
    node "$health_check"
)
printf '%s\n' "$preflight_health"
case "$preflight_health" in
  *"entry=loaded"*) entry_health_required=1 ;;
  *"entry=absent"*) entry_health_required=0 ;;
  *)
    echo "ERROR: could not determine pre-install config-entry health." >&2
    exit 1
    ;;
esac

verify_post_restart() {
  if [ "$entry_health_required" -eq 1 ]; then
    HA_HEALTH_TIMEOUT_MS=180000 \
      HA_HEALTH_INITIAL_DELAY_MS=10000 \
      HA_HEALTH_ENTRY_DOMAIN=home_energy_monitor \
      HA_HEALTH_ALLOW_MISSING_ENTRY=0 \
      node "$health_check"
  else
    HA_HEALTH_TIMEOUT_MS=180000 \
      HA_HEALTH_INITIAL_DELAY_MS=10000 \
      HA_HEALTH_ENTRY_DOMAIN="" \
      HA_HEALTH_ALLOW_MISSING_ENTRY=0 \
      node "$health_check"
  fi
}

wait_for_core() {
  HA_HEALTH_TIMEOUT_MS=180000 \
    HA_HEALTH_INITIAL_DELAY_MS=0 \
    HA_HEALTH_ENTRY_DOMAIN="" \
    HA_HEALTH_ALLOW_MISSING_ENTRY=0 \
    node "$health_check"
}

rollback_component_files() {
  ssh -t "$ssh_host" "sudo sh -c '
set -eu
target=/config/custom_components/home_energy_monitor
deployment_root=/config/.home_energy_monitor_deployments
backup=\$deployment_root/backup-${nonce}
failed=\$deployment_root/failed-${nonce}

mkdir -p \"\$deployment_root\"

if [ -e \"\$target\" ]; then
  mv \"\$target\" \"\$failed\"
fi
if [ -e \"\$backup\" ]; then
  mv \"\$backup\" \"\$target\"
fi
'"
}

tar --exclude='__pycache__' --exclude='*.pyc' -C "$source_dir" -czf "$archive" .
echo "Transferring the component archive to $ssh_host."
# Home Assistant's SSH add-on exposes the remote scp binary but does not
# advertise an SFTP subsystem. OpenSSH 9 defaults scp to SFTP, so force its
# compatible legacy transport or the server closes the channel before sudo.
scp -O "$archive" "$ssh_host:$remote_archive"

activation_status=0
ssh -t "$ssh_host" "sudo sh -c '
set -eu
target=/config/custom_components/home_energy_monitor
deployment_root=/config/.home_energy_monitor_deployments
staging=\$deployment_root/staging-${nonce}
backup=\$deployment_root/backup-${nonce}
failed=\$deployment_root/failed-${nonce}
archive=${remote_archive}
activated=0

restore_on_activation_error() {
  status=\$?
  if [ \"\$status\" -ne 0 ]; then
    if [ \"\$activated\" -eq 1 ] && [ -e \"\$target\" ]; then
      mv \"\$target\" \"\$failed\"
    fi
    if [ -e \"\$backup\" ] && [ ! -e \"\$target\" ]; then
      mv \"\$backup\" \"\$target\"
    fi
  fi
  exit \"\$status\"
}
trap restore_on_activation_error 0

mkdir -p \"\$deployment_root\"
mkdir \"\$staging\"
tar -xzf \"\$archive\" -C \"\$staging\"
if [ -e \"\$target\" ]; then
  mv \"\$target\" \"\$backup\"
fi
mv \"\$staging\" \"\$target\"
activated=1
rm -f \"\$archive\"
trap - 0
echo \"Component files activated; returning control to authenticated validation.\"
'" || activation_status=$?

if [ "$activation_status" -ne 0 ]; then
  echo "ERROR: component file activation failed with SSH status $activation_status." >&2
  exit 1
fi

if ! node "$ha_control" check; then
  echo "Home Assistant rejected its configuration; restoring the prior component files." >&2
  if ! rollback_component_files; then
    echo "ERROR: automatic component rollback failed; inspect appliance paths for nonce ${nonce}." >&2
    exit 1
  fi
  if ! node "$ha_control" check; then
    echo "ERROR: prior files were restored, but authenticated configuration validation still fails." >&2
    exit 1
  fi
  echo "ERROR: the new component failed validation; the prior files were restored." >&2
  exit 1
fi

if ! node "$ha_control" restart; then
  echo "Home Assistant did not accept the authenticated restart request; restoring the prior component." >&2
  if ! rollback_component_files; then
    echo "ERROR: automatic component rollback failed; inspect appliance paths for nonce ${nonce}." >&2
    exit 1
  fi
  if ! wait_for_core || ! node "$ha_control" check || ! node "$ha_control" restart; then
    echo "ERROR: prior files were restored, but restart recovery could not be proven." >&2
    exit 1
  fi
  if ! verify_post_restart; then
    echo "ERROR: Home Assistant did not recover after restoring the prior files." >&2
    exit 1
  fi
  echo "ERROR: the new component was rolled back after restart request failure." >&2
  exit 1
fi

if ! verify_post_restart; then
  echo "Home Assistant did not become healthy; restoring the prior component." >&2
  if ! rollback_component_files; then
    echo "ERROR: automatic component rollback failed; inspect appliance paths for nonce ${nonce}." >&2
    exit 1
  fi
  if ! wait_for_core || ! node "$ha_control" check || ! node "$ha_control" restart; then
    echo "ERROR: prior files were restored, but restart recovery could not be initiated." >&2
    exit 1
  fi
  if ! verify_post_restart; then
    echo "ERROR: the prior component was restored, but Home Assistant health did not recover." >&2
    exit 1
  fi
  echo "ERROR: the new component failed health verification; the prior copy was restored and the failed copy is retained." >&2
  exit 1
fi

echo "Home Energy Monitor installed and Home Assistant is healthy. Prior copy, if any: /config/.home_energy_monitor_deployments/backup-${nonce}"
