# Deployment

## Baseline security

AgentNode defaults to loopback. For remote access, prefer a private VPN/overlay plus TLS. If binding beyond loopback, add the intended DNS name/IP to `http.trusted_hosts`. Keep browser CDP bound to loopback and let AgentNode remain the authenticated boundary.

## Windows

Run elevated PowerShell:

```powershell
./scripts/install-windows.ps1
```

The Core service is a boot-time Windows service (`start= auto`, LocalSystem) and is reachable without any logon. The Desktop Worker belongs in the interactive user session. Office COM, UIA, screenshots and input should execute through that worker rather than Session 0.

Mesh peer tokens for the Core service are read from `C:\ProgramData\AgentNode\service.env` (written by the installer from `AGENTNODE_PEER_*` variables at install time, editable afterwards). Service logs go to `serve.log` in the same directory.

For production, install Python/AgentNode into a machine-readable path such as `C:\Program Files\AgentNode`, not a user-only virtual environment.

Optional deep-operation install:

```powershell
pip install -e '.[mcp,documents,browser,windows,office,ocr]'
```

## Multi-node mesh (Linux, verified 4-node)

A stable pattern for a coordinated fleet across NAT boundaries (public node with an
inside-LAN group behind hairpin-unfriendly NAT):

- One shared RBAC hash triplet (`operator` / `super` / `node`) on every node's
  `config.yaml`; peers authenticate with the raw **node** token.
- Every peer is declared as `mesh.peers.<name> = {url, token_env}`; the token value
  lives only in the 0600 `service.env` (name `AGENTNODE_PEER_<NAME>_TOKEN`), never in
  `config.yaml`.
- Each `mesh.peers.<name>.url` is the *reliable* path to that peer: a direct LAN IP
  when the return path works, or `http://127.0.0.1:<tunnel-port>` when it must ride a
  reverse-SSH tunnel (hairpin NAT frequently blocks "public-IP-from-inside").
- Tunnels are plain user-scope systemd units running `ssh -N -R/-L -o
  ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3`,
  `Restart=on-failure`, enabled at boot (Linger required for user units).
- Every node reports peers via `GET /api/v1/peers` and accepts 1:1 delegate plus
  1:N coordinate fan-out (requires `mesh.delegate` scope).

Example tunnel topology that was verified live (debian coordinator, `zjdebian10`
CT, `ser117` public node, `win10` VM):

```text
debian --direct---------> zjdebian10 (10.88.92.223:8765)
debian --direct---------> win10     (192.168.122.4:8765)
debian --ssh -L 18763 --> ser117    (127.0.0.1:18763)  [debian ssh client]
zj     --ssh -R 18764 --> local     (127.0.0.1:18764)  [zj ssh client to debian]
ser117 sees:
  local    via 127.0.0.1:18766   (debian ssh -R)
  zj       via 127.0.0.1:18765   (zj ssh -R)
  win10    via 127.0.0.1:18767   (debian ssh -R, binding 192.168.122.4:8765)
```

Coordinating from any node: POST `/api/v1/mesh/coordinate` (or the
`agentnode mesh-coordinate --peer ... --command ...` CLI) fans out to all peers and
aggregates results, so a single coordinator can autonomously dispatch work across
the whole fleet in one call.

## Linux

```bash
sudo ./scripts/install-linux.sh /opt/agentnode/config.yaml
```

The systemd unit is hardened; privileged operations may require an intentional change of `User=`/capabilities. It starts at boot (`multi-user.target`), anchors a fixed `WorkingDirectory`, and reads mesh peer tokens from the optional `/etc/agentnode/service.env`. Use `scripts/smoke-posix.sh` after deployment.

## macOS

```bash
sudo ./scripts/install-macos.sh /Library/Application\ Support/AgentNode/config.yaml
```

Grant Accessibility/Screen Recording only to the interactive desktop component that requires it.
