#!/usr/bin/env bash
set -euo pipefail
CONFIG=${1:-'/Library/Application Support/AgentNode/config.yaml'}
PYTHON=${PYTHON:-$(command -v python3)}
mkdir -p "$(dirname "$CONFIG")"
[[ -f "$CONFIG" ]] || "$PYTHON" -m agentnode init --config "$CONFIG"
cat >/Library/LaunchDaemons/com.agentnode.core.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Label</key><string>com.agentnode.core</string><key>ProgramArguments</key><array><string>$PYTHON</string><string>-m</string><string>agentnode</string><string>serve</string><string>--config</string><string>$CONFIG</string></array><key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>
EOF
launchctl bootstrap system /Library/LaunchDaemons/com.agentnode.core.plist || true
