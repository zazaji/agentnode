#!/usr/bin/env bash
# AgentNode 3.2 Linux installer: registers a boot-time systemd unit.
# The service starts at multi-user.target (machine boot), independent of any user
# login, with a stable working directory so relative data/allowed_roots paths
# resolve consistently no matter where the unit is started from.
set -euo pipefail
CONFIG=${1:-/etc/agentnode/config.yaml}
PYTHON=${PYTHON:-$(command -v python3)}
WORKDIR=${WORKDIR:-/var/lib/agentnode}
mkdir -p "$(dirname "$CONFIG")" "$WORKDIR"
if [[ ! -f "$CONFIG" ]]; then "$PYTHON" -m agentnode init --config "$CONFIG"; fi
cat >/etc/systemd/system/agentnode.service <<EOF
[Unit]
Description=AgentNode 3.0 Core
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$WORKDIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON -m agentnode serve --config $CONFIG
Restart=on-failure
RestartSec=3
NoNewPrivileges=false
ProtectHome=false
# EnvironmentFile allows mesh peer tokens without editing the unit:
#   echo 'AGENTNODE_PEER_DEBIAN_TOKEN=x' > /etc/agentnode/service.env
EnvironmentFile=-/etc/agentnode/service.env
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now agentnode
echo "AgentNode boot-time service installed (multi-user.target). Config: $CONFIG"
