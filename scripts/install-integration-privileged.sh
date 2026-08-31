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
  rm -f \"\$archive\"
  echo \"Home Assistant rejected the component; the prior copy was restored.\" >&2
  exit 10
fi
if ! /usr/bin/ha core restart; then
  rollback_component
  /usr/bin/ha core restart || true
  rm -f \"\$archive\"
  echo \"Restart failed; the prior copy was restored and the failed copy is at \$failed.\" >&2
  exit 11
fi
rm -f \"\$archive\"
echo \"Component activated; waiting for authenticated Home Assistant health.\"
'" || activation_status=$?

case "$activation_status" in
  0) ;;
  10 | 11)
    if ! verify_post_restart; then
      echo "ERROR: the prior component was restored, but authenticated recovery verification failed." >&2
      exit 1
    fi
    echo "ERROR: component activation failed; the prior component was restored and verified healthy." >&2
    exit 1
    ;;
  *)
    echo "ERROR: component activation failed unexpectedly with SSH status $activation_status; recovery could not be proven." >&2
    exit 1
    ;;
esac

if ! verify_post_restart; then
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
  if ! verify_post_restart; then
    echo "ERROR: the prior component was restored, but Home Assistant health did not recover." >&2
    exit 1
  fi
  echo "ERROR: the new component failed health verification; the prior copy was restored and the failed copy is retained." >&2
  exit 1
fi

echo "Home Energy Monitor installed and Home Assistant is healthy. Prior copy: /config/custom_components/.home_energy_monitor.backup-${nonce}"
