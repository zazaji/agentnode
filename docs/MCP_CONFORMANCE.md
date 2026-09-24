# MCP Conformance

AgentNode serves MCP over HTTP and stdio. Protocol behavior is validated against the official `@modelcontextprotocol/conformance` scenario runner in the private project workspace; the runner and its loopback-only fixture are not published with the public repository.

## Server posture

- `/mcp` (streamable HTTP) and MCP stdio use the same RBAC scopes as the REST API.
- Unauthenticated posts are rejected (`401`); tool calls answer `isError` with `403 scope required: ...` when the caller lacks the scope.
- CI (`ci.yml`) runs `compileall` on `src` and builds the wheel; it does not execute the conformance runner.

Production `/mcp` remains authenticated.

## Authentication note

AgentNode 3.2+ production mode uses scoped static Bearer tokens. This is not represented as full OAuth 2.1 MCP resource-server conformance. A future OAuth/OIDC resource-server provider must add protected-resource metadata, audience-bound access-token validation and the associated official auth conformance suite before a Tier claim is made.
