# Third-Party Notices

## Desktop Commander MCP

AgentNode 3.x includes behavior-level ports and design ideas derived from
Desktop Commander MCP v0.2.51, especially around progressive search sessions,
terminal/process sessions, bounded output history, file-type-aware reading,
fuzzy edit fallback, configuration ergonomics, and local tool-call history.

Source project: `wonderwhy-er/DesktopCommanderMCP`

MIT License

Copyright (c) 2024-2025 Eduard Ruzga and Desktop Commander Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### Implementation note

AgentNode is Python while Desktop Commander is TypeScript. The 3.1 work is a
Python reimplementation/port of selected behaviors and algorithms rather than
a byte-for-byte copy. The notice is retained deliberately because some
behavior and implementation structure was studied directly from the MIT
licensed source supplied for this work.
