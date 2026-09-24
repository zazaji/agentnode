# MCP Conformance

AgentNode integrates the official `@modelcontextprotocol/conformance` framework in `.github/workflows/mcp-conformance.yml`.

## CI strategy

- strict gate: official `server-initialize` scenario;
- visibility job: complete current `active` server suite, saved as a workflow artifact;
- the fixture in `scripts/mcp_conformance_server.py` is loopback-only and intentionally bypasses production Bearer authentication so protocol behavior can be measured independently.

Production `/mcp` remains authenticated.

## Authentication note

AgentNode 3.2 production mode uses scoped static Bearer tokens. This is not represented as full OAuth 2.1 MCP resource-server conformance. A future OAuth/OIDC resource-server provider must add protected-resource metadata, audience-bound access-token validation and the associated official auth conformance suite before a Tier claim is made.
