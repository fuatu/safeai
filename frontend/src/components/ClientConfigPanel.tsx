import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Copy,
  Check,
  Download,
  FolderOpen,
  Terminal,
  ExternalLink,
  Sparkles,
  Layers,
  Code2,
  FileCode,
  ShieldAlert,
  ShieldCheck,
  Shield,
} from 'lucide-react';
import { ClientConfigItem, ClientConfigsMap } from '../types';

export const ClientConfigPanel: React.FC = () => {
  const [configs, setConfigs] = useState<ClientConfigsMap | null>(null);
  const [selectedKey, setSelectedKey] = useState<string>('copilot');
  const [port, setPort] = useState<number>(8080);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const fetchConfigs = async (targetPort: number) => {
    try {
      const res = await fetch(`/api/client-configs?port=${targetPort}`);
      if (res.ok) {
        const data: ClientConfigsMap = await res.json();
        setConfigs(data);
      }
    } catch {}
  };

  useEffect(() => {
    fetchConfigs(port);
  }, [port]);

  const handleCopy = (text: string, sectionId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(sectionId);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  const handleDownload = (filename: string, content: Record<string, any>) => {
    const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const activeClient: ClientConfigItem | null = configs ? configs[selectedKey] : null;
  const jsonContent = activeClient ? JSON.stringify(activeClient.config, null, 2) : '';

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 text-white shadow-lg shadow-blue-500/20">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-100 flex items-center gap-2">
              AI Client Setup & Connect Guides <Sparkles className="w-4 h-4 text-cyan-400" />
            </h3>
            <p className="text-xs text-slate-400">
              One-click configurations and governance rules to connect GitHub Copilot, Google Antigravity, Cursor, Windsurf, and Claude.
            </p>
          </div>
        </div>

        {/* Port Adjuster */}
        <div className="flex items-center gap-2.5 self-start md:self-center px-3.5 py-1.5 rounded-xl bg-[#0a0d14] border border-[#1f293d]">
          <span className="text-xs text-slate-400 font-mono">Gateway Port:</span>
          <input
            type="number"
            min="1024"
            max="65535"
            value={port}
            onChange={(e) => setPort(Number(e.target.value) || 8080)}
            className="w-16 px-2 py-0.5 text-xs text-cyan-400 font-mono font-bold bg-[#121824] border border-[#1f293d] rounded text-center focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      {/* Client Name URL Identification Banner */}
      <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-800/40 flex items-start gap-3">
        <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <div className="font-semibold text-cyan-200">
            Explicit AI Client Identification via URL (<code className="text-cyan-400 font-mono">?client_name=...</code>)
          </div>
          <p className="text-slate-400 leading-relaxed">
            SafeAI identifies and isolates connecting AI clients using the <code className="text-cyan-300 font-mono">?client_name=</code> parameter in the MCP endpoint URL (e.g.{' '}
            <code className="text-cyan-300 font-mono">http://localhost:{port}/mcp?client_name=GithubCopilot</code>). Since default MCP client libraries report generic names (<code className="text-slate-300">"mcp"</code>), passing <code className="text-cyan-300 font-mono">?client_name=</code> guarantees your sessions and audit trails are correctly attributed and never grouped as a generic client.
          </p>
        </div>
      </div>

      {/* Client Selector Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { key: 'copilot', name: 'GitHub Copilot', desc: 'VS Code & Agent Mode' },
          { key: 'antigravity', name: 'Google Antigravity', desc: 'Antigravity IDE' },
          { key: 'cursor', name: 'Cursor', desc: 'Cursor IDE & Rules' },
          { key: 'windsurf', name: 'Windsurf', desc: 'Codeium Cascade' },
          { key: 'claude', name: 'Claude Desktop', desc: 'Anthropic Claude' },
          { key: 'generic', name: 'Generic / Custom', desc: 'SSE & OpenAI API' },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setSelectedKey(item.key)}
            className={`p-4 rounded-xl border text-left transition-all ${
              selectedKey === item.key
                ? 'bg-blue-600/10 border-blue-500 text-white shadow-md shadow-blue-600/10'
                : 'bg-[#121824] border-[#1f293d] text-slate-400 hover:text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="font-semibold text-xs text-slate-200 flex items-center justify-between">
              {item.name}
              {selectedKey === item.key && <span className="w-2 h-2 rounded-full bg-blue-500" />}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">{item.desc}</div>
          </button>
        ))}
      </div>

      {/* Active Client Details Card */}
      {activeClient && (
        <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1f293d] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-sm text-slate-100">{activeClient.name}</h4>
                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-blue-950/40 border border-blue-900/50 text-blue-300">
                  {activeClient.filename}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">{activeClient.description}</p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleCopy(jsonContent, 'config-json')}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
              >
                {copiedSection === 'config-json' ? (
                  <>
                    <Check className="w-3.5 h-3.5" /> Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" /> Copy Config
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => handleDownload(activeClient.filename, activeClient.config)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#0a0d14] hover:bg-[#151c2a] border border-[#1f293d] text-slate-200 text-xs font-semibold transition-all active:scale-95"
              >
                <Download className="w-3.5 h-3.5" /> Download JSON
              </button>
            </div>
          </div>

          {/* Quick Command Hint (if any) */}
          {activeClient.command_hint && (
            <div className="p-3.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-mono text-cyan-300 truncate">
                <Terminal className="w-4 h-4 text-cyan-400 shrink-0" />
                <span className="truncate">{activeClient.command_hint}</span>
              </div>
              <button
                type="button"
                onClick={() => handleCopy(activeClient.command_hint!, 'hint')}
                className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-[#121824] transition-colors shrink-0"
                title="Copy command"
              >
                {copiedSection === 'hint' ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          )}

          {/* Target File Paths Guide */}
          {activeClient.target_paths && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                <FolderOpen className="w-4 h-4 text-cyan-400" /> Configuration File Locations:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
                {Object.entries(activeClient.target_paths).map(([osName, filePath]) => (
                  <div
                    key={osName}
                    onClick={() => handleCopy(filePath, `path-${osName}`)}
                    className="p-2.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] flex items-center justify-between gap-2 cursor-pointer hover:border-slate-700 transition-colors group"
                  >
                    <div className="truncate">
                      <span className="text-[10px] uppercase font-semibold text-slate-500 mr-2">
                        [{osName}]
                      </span>
                      <span className="text-slate-300 text-[11px]">{filePath}</span>
                    </div>
                    {copiedSection === `path-${osName}` ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    ) : (
                      <Copy className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Formatted JSON Snippet */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span className="flex items-center gap-1.5">
                <FileCode className="w-3.5 h-3.5 text-blue-400" /> JSON Configuration Snippet
              </span>
            </div>
            <pre className="p-4 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-xs font-mono text-emerald-400 overflow-x-auto max-h-72 whitespace-pre-wrap leading-relaxed">
              {jsonContent}
            </pre>
          </div>

          {/* Enforcement & Bypass Prevention Policy Rule */}
          {activeClient.enforcement_rule && (
            <div className="p-5 rounded-2xl bg-gradient-to-b from-amber-950/20 via-[#0a0d14] to-[#0a0d14] border border-amber-900/40 space-y-4 shadow-lg shadow-amber-950/10">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-amber-900/30 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-sm">
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <div>
                    <h5 className="font-semibold text-xs sm:text-sm text-amber-200 flex items-center gap-2">
                      🛡️ {activeClient.enforcement_rule.title}
                    </h5>
                    <p className="text-[11px] text-slate-400">
                      {activeClient.enforcement_rule.description}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopy(activeClient.enforcement_rule!.content, 'rule-content')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 text-amber-200 text-xs font-semibold transition-all shrink-0 active:scale-95"
                >
                  {copiedSection === 'rule-content' ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied Rule!
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy Policy Rule
                    </>
                  )}
                </button>
              </div>

              {/* Rule Target File Paths */}
              {activeClient.enforcement_rule.rule_files && Object.keys(activeClient.enforcement_rule.rule_files).length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
                    <FolderOpen className="w-3.5 h-3.5 text-amber-400" /> Recommended rule file locations (click to copy path):
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
                    {Object.entries(activeClient.enforcement_rule.rule_files).map(([scope, filePath]) => (
                      <div
                        key={scope}
                        onClick={() => handleCopy(filePath, `rule-path-${scope}`)}
                        className="p-2.5 rounded-xl bg-[#0d111a] border border-[#1f293d] flex items-center justify-between gap-2 cursor-pointer hover:border-amber-600/40 transition-colors group"
                      >
                        <div className="truncate">
                          <span className="text-[10px] uppercase font-semibold text-amber-400/90 mr-2">
                            [{scope}]
                          </span>
                          <span className="text-slate-300 text-[11px]">{filePath}</span>
                        </div>
                        {copiedSection === `rule-path-${scope}` ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-400 shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Formatted Markdown Content */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-medium text-slate-400 flex items-center gap-1.5">
                  <FileCode className="w-3.5 h-3.5 text-amber-400" /> Rule Content (Markdown):
                </div>
                <pre className="p-3.5 rounded-xl bg-[#06080d] border border-amber-900/30 text-xs font-mono text-amber-100/90 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                  {activeClient.enforcement_rule.content}
                </pre>
              </div>

              {/* Optional Setting Hint */}
              {activeClient.enforcement_rule.setting_hint && (
                <div className="p-3 rounded-xl bg-[#0d111a] border border-[#1f293d] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 text-[11px]">
                      Recommended defense-in-depth setting (<code className="text-slate-300">{activeClient.enforcement_rule.setting_hint.path}</code>):
                    </span>
                    <pre className="text-cyan-300 font-mono text-[11px] mt-1">
                      {activeClient.enforcement_rule.setting_hint.snippet}
                    </pre>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopy(activeClient.enforcement_rule!.setting_hint!.snippet, 'setting-hint')}
                    className="self-start sm:self-center px-2.5 py-1.5 rounded-lg bg-[#161d2b] hover:bg-[#1e2738] border border-slate-700 text-slate-300 text-[11px] font-mono shrink-0 transition-colors"
                  >
                    {copiedSection === 'setting-hint' ? 'Copied!' : 'Copy Setting'}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Step-by-Step Setup Guide */}
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 space-y-3 text-xs text-slate-300">
            <div className="font-semibold text-slate-200">How to activate:</div>
            {selectedKey === 'claude' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  Open <strong>Claude Desktop</strong> &rarr; Click <code>Settings</code> &rarr;{' '}
                  <code>Developer</code> &rarr; <code>Edit Config</code>.
                </li>
                <li>
                  Paste the JSON snippet above into your <code>claude_desktop_config.json</code> file.
                </li>
                <li>Restart Claude Desktop. SafeAI is now actively protecting Claude!</li>
              </ol>
            )}
            {selectedKey === 'copilot' && (
              <div className="space-y-3">
                <div className="text-slate-200 font-medium">Step-by-step setup for GitHub Copilot in VS Code:</div>

                <div className="p-3.5 rounded-xl bg-blue-950/20 border border-blue-900/40 space-y-2">
                  <div className="font-semibold text-cyan-400 flex items-center justify-between">
                    <span>Step 1: Add SafeAI MCP Server</span>
                    <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">Recommended</span>
                  </div>
                  <p className="text-[11px] text-slate-300">
                    In VS Code Command Palette (<kbd className="font-mono text-cyan-300">Cmd+Shift+P</kbd> / <kbd className="font-mono text-cyan-300">Ctrl+Shift+P</kbd>):
                  </p>
                  <ol className="list-decimal list-inside space-y-1 text-slate-300 text-xs">
                    <li>
                      Run <strong>"Add MCP Server"</strong> &rarr; Select <strong className="text-white">HTTP (HTTP or Server-Sent Events)</strong>.
                    </li>
                    <li>
                      Server Name / ID: enter <code className="text-cyan-300 font-bold">safeai</code>.
                    </li>
                    <li>
                      Server URL: enter <code className="text-cyan-300 font-bold">http://localhost:{port}/mcp?client_name=GithubCopilot</code>.
                    </li>
                  </ol>
                  <p className="text-[11px] text-slate-400 pt-1 border-t border-blue-900/30">
                    <em>Alternative:</em> Paste the JSON snippet into <code className="text-slate-300">.vscode/mcp.json</code> in your project workspace root.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-900/40 space-y-2">
                  <div className="font-semibold text-amber-300 flex items-center justify-between">
                    <span>Step 2: Add Enforcement Policy (Mandatory)</span>
                    <span className="text-[10px] uppercase px-1.5 py-0.5 rounded bg-amber-950 border border-amber-800 text-amber-300">Security</span>
                  </div>
                  <p className="text-[11px] text-slate-300">
                    To prevent Copilot Chat from using unmonitored built-in terminal tools (<code className="text-amber-200">#terminal</code> or <code className="text-amber-200">runInTerminal</code>), copy the <strong>SafeAI Security & Execution Policy</strong> above into:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-slate-400 text-xs">
                    <li>Workspace: <code className="text-slate-200">.github/copilot-instructions.md</code></li>
                    <li>Global: <code className="text-slate-200">~/.copilot/copilot-instructions.md</code></li>
                  </ul>
                </div>

                <p className="text-slate-400 text-[11px]">
                  Once connected, Copilot Chat in Agent mode will run all tool calls through SafeAI for risk analysis and human authorization.
                </p>
              </div>
            )}
            {selectedKey === 'antigravity' && (
              <div className="space-y-3">
                <div className="text-slate-200 font-medium">Step-by-step setup for Google Antigravity IDE:</div>
                <div className="p-3.5 rounded-xl bg-blue-950/20 border border-blue-900/40 space-y-2">
                  <div className="font-semibold text-cyan-400">Step 1: Add MCP Configuration</div>
                  <ol className="list-decimal list-inside space-y-1 text-slate-300 text-xs">
                    <li>
                      Open or create <code className="text-slate-200">.agents/mcp_config.json</code> in your workspace root (or globally at <code className="text-slate-200">~/.gemini/antigravity-ide/mcp_config.json</code>).
                    </li>
                    <li>Paste the JSON snippet above (includes <code className="text-cyan-300 font-mono">?client_name=antigravity</code>).</li>
                  </ol>
                </div>
                <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-900/40 space-y-2">
                  <div className="font-semibold text-amber-300">Step 2: Enforce Mandatory SafeAI Routing</div>
                  <p className="text-[11px] text-slate-300">
                    Antigravity provides a native <code className="text-amber-200">run_command</code> tool. To guarantee the agent cannot bypass SafeAI, add the <strong>SafeAI Governance & Execution Policy</strong> above into:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-slate-400 text-xs">
                    <li>Global: <code className="text-slate-200">~/.gemini/config/GEMINI.md</code> (recommended for all projects)</li>
                    <li>Workspace: <code className="text-slate-200">.agents/rules/safeai_policy.md</code></li>
                  </ul>
                </div>
              </div>
            )}
            {selectedKey === 'cursor' && (
              <div className="space-y-3">
                <div className="text-slate-200 font-medium">Step-by-step setup for Cursor IDE:</div>
                <div className="p-3.5 rounded-xl bg-blue-950/20 border border-blue-900/40 space-y-2">
                  <div className="font-semibold text-cyan-400">Step 1: Configure MCP Server</div>
                  <ol className="list-decimal list-inside space-y-1 text-slate-300 text-xs">
                    <li>
                      In <strong>Cursor</strong>, go to <code>Settings</code> &rarr; <code>Features</code> &rarr; <code>MCP</code> &rarr; <strong>Add New MCP Server</strong>.
                    </li>
                    <li>
                      Set Name: <code className="text-cyan-300 font-bold">safeai</code> | Type: <code className="text-cyan-300 font-bold">SSE</code> | URL: <code className="text-cyan-300 font-bold">http://localhost:{port}/mcp?client_name=Cursor</code>.
                    </li>
                    <li>
                      Or add to <code className="text-slate-200">.cursor/mcp.json</code> in your project root.
                    </li>
                  </ol>
                </div>
                <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-900/40 space-y-2">
                  <div className="font-semibold text-amber-300">Step 2: Add Cursor AI Rule</div>
                  <p className="text-[11px] text-slate-300">
                    Add the <strong>Cursor AI Security Policy</strong> above to <code className="text-slate-200">.cursorrules</code> or <code className="text-slate-200">.cursor/rules/safeai.mdc</code> so Cursor Agent routes all shell commands through SafeAI.
                  </p>
                </div>
              </div>
            )}
            {selectedKey === 'windsurf' && (
              <div className="space-y-3">
                <div className="text-slate-200 font-medium">Step-by-step setup for Windsurf (Codeium Cascade):</div>
                <div className="p-3.5 rounded-xl bg-blue-950/20 border border-blue-900/40 space-y-2">
                  <div className="font-semibold text-cyan-400">Step 1: Configure MCP in Windsurf</div>
                  <ol className="list-decimal list-inside space-y-1 text-slate-300 text-xs">
                    <li>
                      In <strong>Windsurf</strong>, open <code>Settings</code> &rarr; <code>Cascade</code> &rarr; <code>MCP Plugins</code>.
                    </li>
                    <li>
                      Or paste the JSON snippet above into <code className="text-slate-200">~/.codeium/windsurf/mcp_config.json</code>.
                    </li>
                  </ol>
                </div>
                <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-900/40 space-y-2">
                  <div className="font-semibold text-amber-300">Step 2: Add Windsurf Rules</div>
                  <p className="text-[11px] text-slate-300">
                    Add the <strong>Windsurf Security Policy</strong> above to <code className="text-slate-200">.windsurfrules</code> in your project root to force Cascade to execute tools via SafeAI.
                  </p>
                </div>
              </div>
            )}
            {selectedKey === 'generic' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  Point any MCP client to <code>http://localhost:{port}/mcp?client_name=CustomAgent</code> (SSE transport).
                </li>
                <li>
                  Point any OpenAI-compatible agent (LangChain, AutoGen, CrewAI) to Base URL{' '}
                  <code>http://localhost:{port}/v1</code> with API Key <code>safeai-local-key</code>.
                </li>
                <li>All tool executions will be audited and held whenever risk exceeds threshold.</li>
              </ol>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
