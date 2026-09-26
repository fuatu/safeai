import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Activity,
  Sliders,
  History,
  Radio,
  RefreshCw,
  Terminal,
} from 'lucide-react';
import { useSafeAIWebSocket } from './hooks/useSafeAIWebSocket';
import { ApprovalModal } from './components/ApprovalModal';
import { SessionTimeline } from './components/SessionTimeline';
import { SessionSummary } from './components/SessionSummary';
import { SettingsPanel } from './components/SettingsPanel';
import { ActionLog, SafeAISettings, SessionRecord } from './types';

export const App: React.FC = () => {
  const { isConnected, pendingApprovals, submitDecision } = useSafeAIWebSocket();

  const [activeTab, setActiveTab] = useState<'timeline' | 'settings'>('timeline');
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [actions, setActions] = useState<ActionLog[]>([]);
  const [isLoadingActions, setIsLoadingActions] = useState<boolean>(false);

  const [settings, setSettings] = useState<SafeAISettings>({
    approval_threshold: 50,
    active_language: 'en',
    explainer_mode: 'plain',
    dlp_enabled: true,
    approval_timeout_seconds: 90,
  });

  // Fetch initial settings
  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch {}
  };

  // Fetch recent sessions
  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/sessions');
      if (res.ok) {
        const data: SessionRecord[] = await res.json();
        setSessions(data);
        if (data.length > 0 && !selectedSessionId) {
          setSelectedSessionId(data[0].id);
        }
      }
    } catch {}
  };

  // Fetch actions for selected session
  const fetchActions = async (sessionId: string | null) => {
    if (!sessionId) {
      setActions([]);
      return;
    }
    setIsLoadingActions(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/actions`);
      if (res.ok) {
        const data = await res.json();
        setActions(data);
      }
    } catch {
    } finally {
      setIsLoadingActions(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchSessions();
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      fetchActions(selectedSessionId);
    }
  }, [selectedSessionId]);

  // Periodic polling for fresh timeline events if WebSocket is reconnecting
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedSessionId) {
        fetchActions(selectedSessionId);
      }
      fetchSessions();
    }, 4000);
    return () => clearInterval(interval);
  }, [selectedSessionId]);

  const handleUpdateSettings = async (updates: Partial<SafeAISettings>) => {
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        const updated = await res.json();
        setSettings(updated);
      }
    } catch {}
  };

  const selectedSession = sessions.find((s) => s.id === selectedSessionId) || null;
  const totalActions = selectedSession ? selectedSession.total_actions : actions.length;
  const blockedActions = selectedSession
    ? selectedSession.blocked_actions
    : actions.filter((a) => a.risk_score >= settings.approval_threshold || a.status === 'REJECTED').length;

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-[#0d121d]/90 backdrop-blur-md border-b border-[#1f293d]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-base tracking-tight text-white">SafeAI</h1>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400">
                    CORE GATEWAY
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-mono">Agent Security & Explainer Governance</p>
              </div>
            </div>

            {/* Connection Status Badge */}
            <div className="hidden sm:flex items-center gap-2 ml-4 px-3 py-1 rounded-full bg-[#121824] border border-[#1f293d] text-xs font-mono">
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`}
              />
              <span className="text-slate-300">
                {isConnected ? 'LIVE WEBSOCKET' : 'CONNECTING...'}
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('timeline')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'timeline'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#121824]'
              }`}
            >
              <Activity className="w-4 h-4" /> Live Activity
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('settings')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'settings'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#121824]'
              }`}
            >
              <Sliders className="w-4 h-4" /> Policy Settings
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 space-y-6">
        {/* Active Pending Approvals Alert Bar (if any) */}
        {pendingApprovals.length > 0 && (
          <div className="p-4 rounded-2xl bg-red-950/40 border border-red-900/60 flex items-center justify-between animate-urgent-glow">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-red-500/20 text-red-400">
                <Radio className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-red-200">
                  {pendingApprovals.length} High-Risk Action(s) Held for Decision
                </h4>
                <p className="text-xs text-red-300/80">
                  Downstream client connections are suspended awaiting your review.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tab 1: Live Timeline & Monitor */}
        {activeTab === 'timeline' && (
          <div className="space-y-6">
            {/* Session Stats Summary Cards */}
            <SessionSummary
              session={selectedSession}
              totalActions={totalActions}
              blockedActions={blockedActions}
            />

            {/* Session Switcher & Timeline Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold text-base text-slate-100 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-blue-400" /> Intercepted Invocations
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    fetchSessions();
                    if (selectedSessionId) fetchActions(selectedSessionId);
                  }}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-[#121824] transition-colors"
                  title="Refresh activity"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Session Selector Dropdown */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                  <History className="w-3.5 h-3.5" /> Session:
                </span>
                <select
                  value={selectedSessionId || ''}
                  onChange={(e) => setSelectedSessionId(e.target.value)}
                  className="px-3 py-1.5 text-xs rounded-xl bg-[#121824] border border-[#1f293d] text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                >
                  {sessions.length === 0 ? (
                    <option value="">No sessions recorded</option>
                  ) : (
                    sessions.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.client_name} · {s.id.slice(0, 10)}... (
                        {new Date(s.started_at).toLocaleTimeString()})
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            {/* Timeline Stream */}
            <SessionTimeline actions={actions} isLoading={isLoadingActions} />
          </div>
        )}

        {/* Tab 2: Policy Settings */}
        {activeTab === 'settings' && (
          <SettingsPanel settings={settings} onUpdateSettings={handleUpdateSettings} />
        )}
      </main>

      {/* Live Sub-100ms Approval Modal (Renders if any pending action exists) */}
      {pendingApprovals.length > 0 && (
        <ApprovalModal
          approval={pendingApprovals[0]}
          explainerMode={settings.explainer_mode}
          onApprove={(id, notes) => submitDecision(id, 'APPROVE', notes)}
          onDeny={(id, notes) => submitDecision(id, 'DENY', notes)}
        />
      )}
    </div>
  );
};

export default App;
