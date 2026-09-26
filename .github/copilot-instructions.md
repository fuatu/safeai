# SafeAI Security & Execution Policy for GitHub Copilot

- For all terminal and shell commands, exclusively use the `safeai` MCP tools (`safeai/bash`).
- Do not execute commands directly via unmonitored built-in terminal tools (`#terminal` / `runInTerminal`).
- If SafeAI requests confirmation or halts on high risk, respect the governance gateway's decision.
