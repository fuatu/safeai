import React, { useState, useEffect } from 'react';
import { Sliders, Shield, Globe, Clock, Plus, Trash2, CheckCircle2, Lock } from 'lucide-react';
import { PolicyRule, SafeAISettings } from '../types';

interface SettingsPanelProps {
  settings: SafeAISettings;
  onUpdateSettings: (newSettings: Partial<SafeAISettings>) => Promise<void>;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ settings, onUpdateSettings }) => {
  const [formData, setFormData] = useState<SafeAISettings>(settings);
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [newRulePattern, setNewRulePattern] = useState('');
  const [newRuleType, setNewRuleType] = useState<PolicyRule['rule_type']>('DENY_COMMAND');
  const [isSaved, setIsSaved] = useState(false);

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

  useEffect(() => {
    fetchRules();
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

  return (
    <div className="space-y-8">
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
              Actions scoring $\ge$ {formData.approval_threshold} will suspend connection for human approval.
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
              <option value="en">English (Default)</option>
              <option value="tr">Türkçe (Turkish)</option>
              <option value="es">Español (Spanish)</option>
              <option value="de">Deutsch (German)</option>
              <option value="fr">Français (French)</option>
              <option value="auto">Auto-detect system locale</option>
            </select>
            <p className="text-[11px] text-slate-500">
              Plain-language summaries and warning alerts will be localized in this language.
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

          {/* Approval Timeout Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="text-slate-300 font-medium flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-purple-400" /> Approval Timeout Window:
              </label>
              <span className="font-mono text-purple-400 font-bold bg-[#0a0d14] px-2.5 py-0.5 rounded border border-[#1f293d]">
                {formData.approval_timeout_seconds} seconds
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="300"
              step="5"
              value={formData.approval_timeout_seconds}
              onChange={(e) =>
                setFormData({ ...formData, approval_timeout_seconds: Number(e.target.value) })
              }
              className="w-full accent-purple-500 cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Actions unreviewed after {formData.approval_timeout_seconds}s will auto-reject fail-closed.
            </p>
          </div>
        </div>
      </form>

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
