import React, { useState, useEffect } from 'react';
import { Sliders, Shield, Globe, Clock, Plus, Trash2, CheckCircle2, Lock, Wrench, Server, Check, X, Cpu } from 'lucide-react';
import { PolicyRule, SafeAISettings, ToolSetting } from '../types';

interface SettingsPanelProps {
  settings: SafeAISettings;
  onUpdateSettings: (newSettings: Partial<SafeAISettings>) => Promise<void>;
  onNavigateToClients?: () => void;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ settings, onUpdateSettings, onNavigateToClients }) => {
  const [formData, setFormData] = useState<SafeAISettings>(settings);
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [newRulePattern, setNewRulePattern] = useState('');
  const [newRuleType, setNewRuleType] = useState<PolicyRule['rule_type']>('DENY_COMMAND');
  const [isSaved, setIsSaved] = useState(false);

  // Tool settings state
  const [toolSettings, setToolSettings] = useState<ToolSetting[]>([]);
  const [newToolName, setNewToolName] = useState('');
  const [newCustomThreshold, setNewCustomThreshold] = useState<string>('');
  const [newDownstreamUrl, setNewDownstreamUrl] = useState('');
  const [newBypassApproval, setNewBypassApproval] = useState(false);
  const [newTimeoutMs, setNewTimeoutMs] = useState(15000);
  const [newIsEnabled, setNewIsEnabled] = useState(true);
  const [newDescription, setNewDescription] = useState('');

  useEffect(() => {
    setFormData(settings);
  }, [settings]);

  // Fetch policy rules
  const fetchRules = async () => {
    try {
      const res = await fetch('/api/policy/rules');
      if (res.ok) {
        const data = await res.json();
        setRules(data);
      }
    } catch {}
  };

  // Fetch tool settings
  const fetchToolSettings = async () => {
    try {
      const res = await fetch('/api/tools/settings');
      if (res.ok) {
        const data = await res.json();
        setToolSettings(data);
      }
    } catch {}
  };

  useEffect(() => {
    fetchRules();
    fetchToolSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    await onUpdateSettings(formData);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2500);
  };

  const handleAddRule = async () => {
    if (!newRulePattern.trim()) return;
    const rule: PolicyRule = {
      id: `rule-${Date.now()}`,
      rule_type: newRuleType,
      pattern: newRulePattern.trim(),
      description: 'Custom rule defined in Web Panel',
      is_active: true,
    };
    try {
      const res = await fetch('/api/policy/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rule),
      });
      if (res.ok) {
        setNewRulePattern('');
        fetchRules();
      }
    } catch {}
  };

  const handleDeleteRule = async (ruleId: string) => {
    try {
      const res = await fetch(`/api/policy/rules/${ruleId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchRules();
      }
    } catch {}
  };

  const handleAddToolSetting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newToolName.trim()) return;
    const setting: ToolSetting = {
      tool_name: newToolName.trim(),
      custom_threshold: newCustomThreshold.trim() !== '' ? Number(newCustomThreshold) : null,
      downstream_url: newDownstreamUrl.trim() || null,
      bypass_approval: newBypassApproval,
      timeout_ms: newTimeoutMs,
      is_enabled: newIsEnabled,
      description: newDescription.trim() || null,
    };
    try {
      const res = await fetch('/api/tools/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(setting),
      });
      if (res.ok) {
        setNewToolName('');
        setNewCustomThreshold('');
        setNewDownstreamUrl('');
        setNewBypassApproval(false);
        setNewTimeoutMs(15000);
        setNewIsEnabled(true);
        setNewDescription('');
        fetchToolSettings();
      }
    } catch {}
  };

  const handleDeleteToolSetting = async (toolName: string) => {
    try {
      const res = await fetch(`/api/tools/settings/${encodeURIComponent(toolName)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchToolSettings();
      }
    } catch {}
  };

  const handleToggleToolStatus = async (tool: ToolSetting) => {
    const updated = { ...tool, is_enabled: !tool.is_enabled };
    try {
      const res = await fetch('/api/tools/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        fetchToolSettings();
      }
    } catch {}
  };

  const isInfiniteTimeout = formData.approval_timeout_seconds === 0;

  return (
    <div className="space-y-8">
      {/* AI Client Quick Connect Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-950/40 via-[#121824] to-[#121824] border border-blue-900/40 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/20 text-blue-400">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-100">Need AI Client Configuration Snippets?</h4>
            <p className="text-[11px] text-slate-400">
              One-click setup configs and guides for Claude Desktop, Google Antigravity, and Cursor.
            </p>
          </div>
        </div>
        {onNavigateToClients && (
          <button
            type="button"
            onClick={onNavigateToClients}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-sm shrink-0 active:scale-95"
          >
            Connect Clients &rarr;
          </button>
        )}
      </div>

      {/* System Governance Controls */}
      <form onSubmit={handleSave} className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-6">
        <div className="flex items-center justify-between border-b border-[#1f293d] pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-base text-slate-100">Governance & Explainer Policies</h3>
              <p className="text-xs text-slate-400">
                Changes apply atomically to subsequent AI agent tool calls without service restart.
              </p>
            </div>
          </div>
          <button
            type="submit"
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md active:scale-95 transition-all"
          >
            {isSaved ? (
              <>
                <CheckCircle2 className="w-4 h-4" /> Saved!
              </>
            ) : (
              'Save & Hot-Reload'
            )}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Risk Threshold Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="text-slate-300 font-medium flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-amber-400" /> Human Approval Threshold:
              </label>
              <span className="font-mono text-amber-400 font-bold bg-[#0a0d14] px-2.5 py-0.5 rounded border border-[#1f293d]">
                {formData.approval_threshold} / 100
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={formData.approval_threshold}
              onChange={(e) => setFormData({ ...formData, approval_threshold: Number(e.target.value) })}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Actions scoring &ge; {formData.approval_threshold} will suspend connection for human approval.
            </p>
          </div>

          {/* Active Language Selector */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
              <Globe className="w-4 h-4 text-blue-400" /> Active Language (For Dummies Explainer):
            </label>
            <select
              value={formData.active_language}
              onChange={(e) => setFormData({ ...formData, active_language: e.target.value })}
              className="w-full px-3.5 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="auto">Auto-detect from conversation context & locale</option>
              <option value="en">English (Default)</option>
              <option value="tr">Türkçe (Turkish)</option>
              <option value="es">Español (Spanish)</option>
              <option value="de">Deutsch (German)</option>
              <option value="fr">Français (French)</option>
            </select>
            <p className="text-[11px] text-slate-500">
              Plain-language summaries dynamically adapt to user conversation (Turkish, German, Spanish, etc.) or fall back to system locale.
            </p>
          </div>

          {/* Explainer Mode */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
              Explainer Display Mode:
            </label>
            <select
              value={formData.explainer_mode}
              onChange={(e) => setFormData({ ...formData, explainer_mode: e.target.value as any })}
              className="w-full px-3.5 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="plain">Plain Language (Prioritizes simple real-world explanation)</option>
              <option value="technical">Technical (Prioritizes raw terminal command diffs)</option>
              <option value="off">Off (Suppresses plain language)</option>
            </select>
          </div>

          {/* Approval Timeout Slider (with Infinite option) */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="text-slate-300 font-medium flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-purple-400" /> Approval Timeout Window:
              </label>
              <span className="font-mono text-purple-400 font-bold bg-[#0a0d14] px-2.5 py-0.5 rounded border border-[#1f293d]">
                {isInfiniteTimeout ? '∞ Infinite (No timeout)' : `${formData.approval_timeout_seconds} seconds`}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="300"
              step="5"
              value={formData.approval_timeout_seconds}
              onChange={(e) =>
                setFormData({ ...formData, approval_timeout_seconds: Number(e.target.value) })
              }
              className="w-full accent-purple-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              {isInfiniteTimeout
                ? 'Actions will hold connection indefinitely until explicit manual approval or rejection.'
                : `Actions unreviewed after ${formData.approval_timeout_seconds}s will auto-reject fail-closed.`}
            </p>
          </div>
        </div>
      </form>

      {/* MCP Tool Governance (Per-Tool & Generic) */}
      <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-6">
        <div className="flex items-center gap-3 border-b border-[#1f293d] pb-4">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400">
            <Wrench className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-100">MCP Tool Governance & Routing</h3>
            <p className="text-xs text-slate-400">
              Configure per-tool security thresholds, downstream endpoints, bypass rules, and generic wildcard (<code>*</code>) fallback.
            </p>
          </div>
        </div>

        {/* Add/Configure Tool Setting Form */}
        <form onSubmit={handleAddToolSetting} className="p-4 rounded-xl bg-[#0a0d14] border border-[#1f293d] space-y-4">
          <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Server className="w-4 h-4 text-blue-400" /> Add or Update Tool Configuration
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Tool Name (* for generic fallback)</label>
              <input
                type="text"
                placeholder="e.g. bash, * or fetch"
                value={newToolName}
                onChange={(e) => setNewToolName(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-[#121824] border border-[#1f293d] text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Custom Threshold (0-100, blank = default)</label>
              <input
                type="number"
                min="0"
                max="100"
                placeholder="Global default"
                value={newCustomThreshold}
                onChange={(e) => setNewCustomThreshold(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-[#121824] border border-[#1f293d] text-slate-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Downstream URL (optional)</label>
              <input
                type="url"
                placeholder="http://localhost:8000/mcp"
                value={newDownstreamUrl}
                onChange={(e) => setNewDownstreamUrl(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-[#121824] border border-[#1f293d] text-slate-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Timeout (ms)</label>
              <input
                type="number"
                min="1000"
                step="1000"
                value={newTimeoutMs}
                onChange={(e) => setNewTimeoutMs(Number(e.target.value))}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-[#121824] border border-[#1f293d] text-slate-200 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-center">
            <div className="sm:col-span-2">
              <input
                type="text"
                placeholder="Description or notes (e.g. Core bash executor or generic fallback)"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg bg-[#121824] border border-[#1f293d] text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex items-center gap-4 justify-end">
              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newBypassApproval}
                  onChange={(e) => setNewBypassApproval(e.target.checked)}
                  className="rounded bg-[#121824] border-[#1f293d] text-blue-500 focus:ring-0"
                />
                Bypass HITL
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newIsEnabled}
                  onChange={(e) => setNewIsEnabled(e.target.checked)}
                  className="rounded bg-[#121824] border-[#1f293d] text-emerald-500 focus:ring-0"
                />
                Enabled
              </label>
              <button
                type="submit"
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-sm transition-all"
              >
                <Plus className="w-3.5 h-3.5" /> Save Tool
              </button>
            </div>
          </div>
        </form>

        {/* Tool Settings List */}
        <div className="space-y-2">
          {toolSettings.length === 0 ? (
            <p className="text-xs text-slate-500 py-3">
              No specific or generic tool settings configured. Global system settings are applied.
            </p>
          ) : (
            toolSettings.map((tool) => (
              <div
                key={tool.tool_name}
                className={`flex flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 rounded-xl border ${
                  tool.tool_name === '*'
                    ? 'bg-blue-950/20 border-blue-900/40'
                    : 'bg-[#0a0d14] border-[#1f293d]'
                } gap-3`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded font-mono font-bold ${
                        tool.tool_name === '*'
                          ? 'bg-blue-600 text-white'
                          : 'bg-[#121824] border border-[#1f293d] text-cyan-300'
                      }`}
                    >
                      {tool.tool_name === '*' ? 'Generic Tool (*)' : tool.tool_name}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium ${
                        tool.is_enabled
                          ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50'
                          : 'bg-red-950/40 text-red-400 border border-red-900/50'
                      }`}
                    >
                      {tool.is_enabled ? 'Active' : 'Disabled'}
                    </span>
                    {tool.bypass_approval && (
                      <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-purple-950/40 text-purple-300 border border-purple-900/50">
                        Bypass Approval
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 font-mono">
                    <span>
                      Threshold:{' '}
                      <strong className="text-slate-200">
                        {tool.custom_threshold !== null ? `${tool.custom_threshold}/100` : 'Default'}
                      </strong>
                    </span>
                    <span>
                      Timeout: <strong className="text-slate-200">{tool.timeout_ms}ms</strong>
                    </span>
                    {tool.downstream_url && (
                      <span className="text-blue-400 truncate max-w-xs">
                        Endpoint: {tool.downstream_url}
                      </span>
                    )}
                    {tool.description && (
                      <span className="text-slate-500 text-[11px] font-sans">
                        — {tool.description}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <button
                    type="button"
                    onClick={() => handleToggleToolStatus(tool)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                      tool.is_enabled
                        ? 'border-amber-900/50 text-amber-300 hover:bg-amber-950/30'
                        : 'border-emerald-900/50 text-emerald-300 hover:bg-emerald-950/30'
                    }`}
                  >
                    {tool.is_enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteToolSetting(tool.tool_name)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Delete setting"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Policy Rules & Guardrails */}
      <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-5">
        <div className="flex items-center gap-3 border-b border-[#1f293d] pb-4">
          <div className="p-2.5 rounded-xl bg-red-500/10 text-red-400">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-100">Deterministic Security Rules</h3>
            <p className="text-xs text-slate-400">
              Explicit blacklist patterns that automatically force high-risk scoring or immediate hold.
            </p>
          </div>
        </div>

        {/* Add new rule form */}
        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={newRuleType}
            onChange={(e) => setNewRuleType(e.target.value as any)}
            className="px-3.5 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-200"
          >
            <option value="DENY_COMMAND">DENY_COMMAND</option>
            <option value="DENY_PATH">DENY_PATH</option>
            <option value="DENY_DOMAIN">DENY_DOMAIN</option>
            <option value="ALLOW_PATH">ALLOW_PATH</option>
          </select>
          <input
            type="text"
            placeholder="Pattern or regex (e.g. 'mkfs.*', '/etc/shadow', 'raw.githubusercontent.com')"
            value={newRulePattern}
            onChange={(e) => setNewRulePattern(e.target.value)}
            className="flex-1 px-3.5 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
          />
          <button
            type="button"
            onClick={handleAddRule}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" /> Add Rule
          </button>
        </div>

        {/* Rule items */}
        <div className="space-y-2">
          {rules.length === 0 ? (
            <p className="text-xs text-slate-500 py-3">No custom rules configured yet.</p>
          ) : (
            rules.map((rule) => (
              <div
                key={rule.id}
                className="flex items-center justify-between p-3 rounded-xl bg-[#0a0d14] border border-[#1f293d]"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-red-950/40 border border-red-900/50 text-red-300">
                    {rule.rule_type}
                  </span>
                  <span className="text-xs font-mono text-slate-200">{rule.pattern}</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteRule(rule.id)}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
