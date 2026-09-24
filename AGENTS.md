# Agent Runtime Guidance

For goal-oriented work on an AgentNode:

1. Inspect current state before changing it.
2. Prefer native/API/UIA operations over pixel interaction.
3. Make the smallest reversible change.
4. After every state-changing action, verify the resulting state independently.
5. Record evidence in the job event stream.
6. Do not reveal tokens, credentials, private clipboard contents, or unrelated files.
7. Avoid destructive actions unless the caller explicitly requested them and policy permits them.
8. For service/config changes: inspect → backup if appropriate → change → restart/reload → health check → report.
9. For desktop work: observe → ground target → act → re-observe → verify.
10. When delegating to another node, preserve trace_id and never delegate back to a node already in hops.
