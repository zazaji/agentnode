# Running the pi Agent on an AgentNode

This is the guide for the person on the receiving end of the packaged
`.deb` / `.whl`. It explains how to turn a node into an automated pi agent:
install a runtime, point pi at an LLM endpoint, enable the AgentNode runtime
entry, then invoke it over the REST API or through the mesh.

It refers to the validated setup used on the reference host (pi CLI + an
OpenAI-compatible/"anthropic-messages" gateway serving a `c_glm` model), so
every key can be copied verbatim and only the endpoint/API-key values need
to change.

## 1. Install an AgentNode

Pick one of the two packages from the download link you were given
(`agentnode_3.2.0_all.deb` or `agentnode-3.2.0-py3-none-any.whl`).

Debian / Ubuntu (install the extra Python deps automatically):

```bash
sudo dpkg -i agentnode_3.2.0_all.deb
sudo apt-get -f install    # pull in python3-fastapi, uvicorn, pydantic, etc.
sudo systemctl daemon-reload
```

Any Python 3.11+ environment (Debian, Ubuntu, other distros, macOS, Windows):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install agentnode-3.2.0-py3-none-any.whl
pip install uvicorn[standard] psutil httpx "pydantic>=2.8" "fastapi>=0.115" PyYAML
```

Optionally install the local agent runtime CLI inside the same environment
so `agent.runtimes.pi` finds it:

```bash
pip install pi`  # or the pi release you were given
```

Verify the server CLI works:

```bash
agentnode --help
```

## 2. Initialize config and tokens

```bash
agentnode init --config /etc/agentnode/agentnode.yaml   # or ./config.yaml
```

`init` prints one-time tokens (operator / super / node / administrator). The
file stores only hashes. Keep the printed values; you will need the
**operator** (or super) token to call `/api/v1/agent`.

Start the server (on the service image, `systemctl start agentnode`):

```bash
agentnode serve --config /etc/agentnode/agentnode.yaml
```

## 3. Point pi at an LLM endpoint

pi reads model providers from `~/.pi/agent/models.json`. The reference host
is wired to a local gateway (`apigate`) that speaks the Anthropic messages
API against a `c_glm` model:

```json
{
  "providers": {
    "apigate": {
      "key": "ANTHROPIC_API_KEY",
      "baseUrl": "http://127.0.0.1:10003",
      "api": "anthropic-messages",
      "models": {
        "c_glm": {
          "id": "c_glm",
          "name": "GLM coding model",
          "contextWindow": 262144,
          "maxTokens": 32768,
          "reasoning": true,
          "vision": ["text", "image"]
        }
      }
    }
  }
}
```

- `key` names the environment variable pi reads the API key from, e.g.
  `ANTHROPIC_API_KEY`. Export it where the AgentNode process runs:
  `export ANTHROPIC_API_KEY=sk-...` (or put it in `/etc/agentnode/service.env`
  for the systemd unit, which loads `EnvironmentFile=-/etc/agentnode/service.env`).
- `baseUrl` / `api` / `model` must match whatever gateway you expose. If you
  use an OpenAI-compatible endpoint, set `"api": "openai"` and adjust the
  model entry accordingly (e.g. `api` naming differs).
- Any runtime whose executable pi cannot find will show `found: false` in
  `GET /api/v1/runtime`.

Test pi directly before connecting it to AgentNode:

```bash
pi --provider apigate --model c_glm --print "reply with OK"
```

## 4. Enable the runtime in AgentNode config

In the config file created in step 2, set:

```yaml
agent:
  default_runtime: pi
  runtimes:
    pi:
      enabled: true
      executable: pi          # resolved via PATH; can be an absolute path
```

Optional keys the runtime manager honors in `agent.runtimes.<name>`:
`enabled`, `executable`, `args` (extra argv appended after `--mode rpc` for
pi, or after the executable for generic runtimes), `env` (extra
`KEY: value` pairs injected into the pi subprocess).

Restart the server, then confirm the runtime is visible:

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/v1/runtime
# {"agents":{"pi":{"enabled":true,"executable":"pi","found":true}},...}
```

`found: false` means pi is not on the server's PATH — install pi into the
same environment the service runs in, or set `executable` to an absolute
path. If `enabled` is `false` (the default shipping config), `/api/v1/agent`
rejects the job with `runtime disabled: pi`.

## 5. Invoke the agent

`POST /api/v1/agent` (scope `agent.run`, held by operator/super) accepts:

| Field        | Type            | Meaning                                    |
| ------------ | --------------- | ------------------------------------------ |
| `prompt`     | string (req.)   | The instruction for the agent              |
| `runtime`    | string, opt.    | `"pi"`, or anything else in `agent.runtimes`; defaults to `agent.default_runtime` |
| `cwd`        | string, opt.    | Working directory for the subprocess       |
| `timeout_s`  | int, opt.       | Default 1800                               |
| `background` | bool, opt.      | Default `true` (returns job handle)        |

Sync:

```bash
curl -s -X POST http://127.0.0.1:8765/api/v1/agent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt":"Read /etc/os-release and say which distro this is","runtime":"pi","background":false}'
```

You get back a job object; on success `state` is `succeeded`, `runtime` is
`pi`, and the events stream contains `agent.rpc` events (each pi RPC frame)
ending with an `agent_settled` frame. Watch progress/listen on events via
`GET /api/v1/jobs/<id>` / the jobs/events endpoints, or the Web Console at
`http://127.0.0.1:8765/`.

Background (returns immediately with the job id):

```bash
curl -s -X POST http://127.0.0.1:8765/api/v1/agent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"prompt":"...","runtime":"pi","background":true}'
```

## 6. Call a remote node's agent through the mesh

If `mesh.delegate` is granted to the caller's role, one node can run the
agent on another:

```bash
curl -s -X POST http://127.0.0.1:8765/api/v1/mesh/delegate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"peer":"win10","action":"agent","payload":{"prompt":"...","runtime":"pi","background":false}}'
```

The router stamps `trace_id`/`hops` on the forwarded request and uses the
peer's token from config or `AGENTNODE_PEER_<name>_TOKEN`, with loop
detection on hops and a `max_hops` limit.

## Troubleshooting

- `runtime disabled: pi` → `agent.runtimes.pi.enabled` is `false`; the
  shipping config ships that way on purpose.
- `found: false` → pi not on PATH of the server process.
- pi subprocess fails to connect → check `~/.pi/agent/models.json`
  `baseUrl`/`api`/model and that the API key env var (`key`) is exported to
  the server process (service.env for systemd).
- Vision questions: the model must accept image input (see `vision` in the
  model entry). pi drives its own file-reading tools on the node; on
  headless Linux ensure the node exposes the paths the prompt references.
