# Contributing

- Python 3.11+.
- Keep platform-specific code under `agentnode/platform` or `agentnode/desktop`.
- Do not weaken scope checks to simplify an integration.
- New state-changing operations need tests and an audit/event story.
- Computer-use providers should implement observation/action interfaces rather than leaking provider types into API routes.
- Run `pytest` and `python -m compileall -q src tests` before opening a change.
