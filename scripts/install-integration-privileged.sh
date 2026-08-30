#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$repo_dir/custom_components/home_energy_monitor"
ssh_host=${HA_SSH_HOST:-homeassistant-ha}
nonce=$(date +%s)
archive=$(mktemp "/tmp/home-energy-monitor-${nonce}-XXXXXX.tar.gz")
remote_archive="/tmp/home-energy-monitor-${nonce}.tar.gz"
health_check="$repo_dir/scripts/wait-for-home-assistant.mjs"

cleanup() {
  rm -f -- "$archive"
}
trap cleanup EXIT

: "${HA_BASE_URL:?Set HA_BASE_URL before running the installer}"
: "${HA_TOKEN:?Set HA_TOKEN before running the installer}"

HA_HEALTH_TIMEOUT_MS=15000 HA_HEALTH_INITIAL_DELAY_MS=0 node "$health_check"

tar --exclude='__pycache__' --exclude='*.pyc' -C "$source_dir" -czf "$archive" .
scp "$archive" "$ssh_host:$remote_archive"

ssh -t "$ssh_host" "sudo sh -c '
set -eu
target=/config/custom_components/home_energy_monitor
staging=/config/custom_components/.home_energy_monitor.staging-${nonce}
backup=/config/custom_components/.home_energy_monitor.backup-${nonce}
failed=/config/custom_components/.home_energy_monitor.failed-${nonce}
archive=${remote_archive}

mkdir \"\$staging\"
tar -xzf \"\$archive\" -C \"\$staging\"
if [ -e \"\$target\" ]; then
  mv \"\$target\" \"\$backup\"
fi
mv \"\$staging\" \"\$target\"

rollback_component() {
  if [ -e \"\$target\" ]; then
    mv \"\$target\" \"\$failed\"
  fi
  if [ -e \"\$backup\" ]; then
    mv \"\$backup\" \"\$target\"
  fi
}

if ! /usr/bin/ha core check; then
  rollback_component
  echo \"Home Assistant rejected the component; the prior copy was restored.\" >&2
  exit 1
fi
if ! /usr/bin/ha core restart; then
  rollback_component
  /usr/bin/ha core restart || true
  echo \"Restart failed; the prior copy was restored and the failed copy is at \$failed.\" >&2
  exit 1
fi
rm -f \"\$archive\"
echo \"Component activated; waiting for authenticated Home Assistant health.\"
'"

if ! HA_HEALTH_TIMEOUT_MS=180000 HA_HEALTH_INITIAL_DELAY_MS=10000 node "$health_check"; then
  echo "Home Assistant did not become healthy; restoring the prior component." >&2
  if ! ssh -t "$ssh_host" "sudo sh -c '
set -eu
target=/config/custom_components/home_energy_monitor
backup=/config/custom_components/.home_energy_monitor.backup-${nonce}
failed=/config/custom_components/.home_energy_monitor.failed-${nonce}

if [ -e \"\$target\" ]; then
  mv \"\$target\" \"\$failed\"
fi
if [ -e \"\$backup\" ]; then
  mv \"\$backup\" \"\$target\"
fi
/usr/bin/ha core check
/usr/bin/ha core restart
'"; then
    echo "ERROR: automatic component rollback failed; inspect appliance paths for nonce ${nonce}." >&2
    exit 1
  fi
  if ! HA_HEALTH_TIMEOUT_MS=180000 HA_HEALTH_INITIAL_DELAY_MS=10000 node "$health_check"; then
    echo "ERROR: the prior component was restored, but Home Assistant health did not recover." >&2
    exit 1
  fi
  echo "ERROR: the new component failed health verification; the prior copy was restored and the failed copy is retained." >&2
  exit 1
fi

echo "Home Energy Monitor installed and Home Assistant is healthy. Prior copy: /config/custom_components/.home_energy_monitor.backup-${nonce}"
