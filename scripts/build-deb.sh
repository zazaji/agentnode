#!/usr/bin/env bash
# Build dist/agentnode_<ver>_all.deb (+ wheel) for the Debian/Ubuntu targets.
# Ships .py sources under /usr/lib/python3/dist-packages + a /usr/bin/agentnode
# wrapper + a boot-time systemd unit + /etc/agentnode/config.example.yaml.
# The unit reads peer tokens from /etc/agentnode/service.env (never the package).
set -euo pipefail
cd "$(dirname "$0")/.."
VER=$(grep -m1 '^version' pyproject.toml | sed -E 's/.*"([0-9.]+)".*/\1/')
DIST=dist; STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
echo "building agentnode $VER"

# --- wheel -------------------------------------------------------------------
uv build --wheel --out-dir "$DIST" -q
echo "wheel: $(ls "$DIST"/agentnode-$VER-py3-none-any.whl)"

# --- deb staging --------------------------------------------------------------
SITE="$STAGE/usr/lib/python3/dist-packages"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/lib/systemd/system" "$STAGE/etc/agentnode" "$SITE"
cp -r src/agentnode "$SITE/agentnode"
find "$SITE" -name '__pycache__' -type d -prune -exec rm -rf {} +

cat >"$STAGE/DEBIAN/control" <<EOF
Package: agentnode
Version: $VER
Architecture: all
Section: utils
Priority: optional
Maintainer: zazaji <zazaji@sina.com>
Depends: python3 (>= 3.11), python3-fastapi, python3-uvicorn, python3-pydantic (>= 2), python3-psutil, python3-httpx, python3-yaml
Description: Cross-platform MCP/REST computer-use agent runtime
 AgentNode is a cross-platform MCP/REST computer-use agent runtime for
 Windows, Linux and macOS: RBAC, jobs, shell/file policy, documents,
 browser (CDP), Windows Office COM, Unified Desktop Graph, agent mesh,
 autonomous mesh coordination, and local MCP. Install to get
 /usr/bin/agentnode, a boot-time systemd unit and
 /etc/agentnode/config.example.yaml.
EOF

cat >"$STAGE/usr/bin/agentnode" <<'EOF'
#!/usr/bin/python3
"""AgentNode CLI entry point (Debian package)."""
import sys
from agentnode.__main__ import main
if __name__ == '__main__':
    sys.exit(main())
EOF
chmod 755 "$STAGE/usr/bin/agentnode"

cat >"$STAGE/lib/systemd/system/agentnode.service" <<EOF
[Unit]
Description=AgentNode runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
StateDirectory=agentnode
WorkingDirectory=/var/lib/agentnode
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-/etc/agentnode/service.env
ExecStart=/usr/bin/agentnode serve --config /etc/agentnode/agentnode.yaml
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "$STAGE/lib/systemd/system/agentnode.service"

cp config.example.yaml "$STAGE/etc/agentnode/config.example.yaml"
chmod 644 "$STAGE/etc/agentnode/config.example.yaml"

mkdir -p "$DIST"
dpkg-deb --root-owner-group --build -Z xz "$STAGE" "$DIST/agentnode_${VER}_all.deb" >/dev/null
echo "deb:  $(ls "$DIST"/agentnode_${VER}_all.deb)"
