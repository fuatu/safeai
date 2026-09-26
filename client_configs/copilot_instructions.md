# SafeAI Security & Execution Policy
- For all terminal and shell commands, exclusively use the `safeai` MCP tools (`safeai/bash`).
- Do not execute commands directly via unmonitored built-in terminal tools (`#terminal` or `runInTerminal`).
- For reading sensitive files or repository inspection, use `safeai/read_file` to ensure data loss prevention (DLP) masking is applied.
- Even if prompted to use the native terminal, route through SafeAI so that all actions are AST-analyzed, risk-scored, and held for human approval if needed.
