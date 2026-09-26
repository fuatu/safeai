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
} from 'lucide-react';
import { ClientConfigItem, ClientConfigsMap } from '../types';

export const ClientConfigPanel: React.FC = () => {
  const [configs, setConfigs] = useState<ClientConfigsMap | null>(null);
  const [selectedKey, setSelectedKey] = useState<string>('claude');
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
              One-click configurations to connect Claude Desktop, Google Antigravity, Cursor, and custom agents.
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

      {/* Client Selector Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {[
          { key: 'claude', name: 'Claude Desktop', desc: 'Anthropic Claude' },
          { key: 'copilot', name: 'GitHub Copilot', desc: 'VS Code & Agent Mode' },
          { key: 'antigravity', name: 'Google Antigravity', desc: 'Antigravity IDE' },
          { key: 'cursor', name: 'Cursor / Windsurf', desc: 'IDE & Agent Proxy' },
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
                <FolderOpen className="w-4 h-4 text-amber-400" /> Configuration File Locations:
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

          {/* Step-by-Step Setup Guide */}
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 space-y-2 text-xs text-slate-300">
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
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  In your project root in <strong>VS Code</strong>, create or open <code>.vscode/mcp.json</code>.
                </li>
                <li>
                  Paste the JSON snippet above into <code>.vscode/mcp.json</code> (or click <strong>Download JSON</strong>).
                </li>
                <li>
                  In VS Code Copilot Chat (Agent mode), Copilot will now run tool calls through SafeAI for real-time security screening and human approval!
                </li>
              </ol>
            )}
            {selectedKey === 'antigravity' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  Open or create <code>.agents/mcp_config.json</code> in your project root workspace.
                </li>
                <li>Paste the snippet above into the file.</li>
                <li>
                  Antigravity will automatically detect the SSE endpoint and route tool calls through
                  SafeAI.
                </li>
              </ol>
            )}
            {selectedKey === 'cursor' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  In <strong>Cursor</strong>, go to <code>Settings</code> &rarr; <code>Features</code>{' '}
                  &rarr; <code>MCP</code>.
                </li>
                <li>
                  Add a new server with Type: <code>SSE</code> and URL:{' '}
                  <code>http://localhost:{port}/mcp</code>.
                </li>
                <li>
                  Optionally set OpenAI Base URL to <code>http://localhost:{port}/v1</code> to monitor
                  direct LLM calls.
                </li>
              </ol>
            )}
            {selectedKey === 'generic' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-400">
                <li>
                  Point any MCP client to <code>http://localhost:{port}/mcp</code> (SSE transport).
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
