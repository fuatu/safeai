import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  Activity,
  Sliders,
  History,
  Radio,
  RefreshCw,
  Terminal,
  Cpu,
  MessageSquare,
} from 'lucide-react';
import { useSafeAIWebSocket } from './hooks/useSafeAIWebSocket';
import { ApprovalModal } from './components/ApprovalModal';
import { SessionTimeline } from './components/SessionTimeline';
import { SessionSummary } from './components/SessionSummary';
import { SettingsPanel } from './components/SettingsPanel';
import { ClientConfigPanel } from './components/ClientConfigPanel';
import { ActionLog, SafeAISettings, SessionRecord } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'settings' | 'clients'>('timeline');
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [actions, setActions] = useState<ActionLog[]>([]);
  const [isLoadingActions, setIsLoadingActions] = useState<boolean>(false);
  const [isSyncingCopilot, setIsSyncingCopilot] = useState<boolean>(false);

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

  // Fetch recent sessions (silent = true prevents unnecessary state reference churn)
  const fetchSessions = async (silent = false) => {
    try {
      const res = await fetch('/api/sessions');
      if (res.ok) {
        const data: SessionRecord[] = await res.json();
        setSessions((prev) => {
          if (
            prev.length === data.length &&
            prev[0]?.id === data[0]?.id &&
            prev[0]?.total_actions === data[0]?.total_actions &&
            prev[0]?.title === data[0]?.title
          ) {
            return prev;
          }
          return data;
        });
        if (data.length > 0 && !selectedSessionId) {
          setSelectedSessionId(data[0].id);
        }
      }
    } catch {}
  };

  // Fetch actions for selected session (silent = true keeps current DOM intact so scroll position never jumps)
  const fetchActions = async (sessionId: string | null, silent = false) => {
    if (!sessionId) {
      setActions([]);
      return;
    }
    if (!silent) {
      setIsLoadingActions(true);
    }
    try {
      const res = await fetch(`/api/sessions/${sessionId}/actions`);
      if (res.ok) {
        const data: ActionLog[] = await res.json();
        setActions((prev) => {
          // If actions are identical, keep existing reference so React does not re-render or reset scroll
          if (
            prev.length === data.length &&
            prev[0]?.id === data[0]?.id &&
            prev[prev.length - 1]?.id === data[data.length - 1]?.id
          ) {
            return prev;
          }
          return data;
        });
      }
    } catch {
    } finally {
      if (!silent) {
        setIsLoadingActions(false);
      }
    }
  };

  // WebSocket action listener for instant live events without full-page reloads
  const handleActionLogged = useCallback((evt: any) => {
    if (!evt.sessionId || evt.sessionId === selectedSessionId) {
      fetchActions(selectedSessionId, true);
    }
    fetchSessions(true);
  }, [selectedSessionId]);

  const { isConnected, pendingApprovals, submitDecision } = useSafeAIWebSocket({
    onActionLogged: handleActionLogged,
  });

  useEffect(() => {
    fetchSettings();
    fetchSessions();
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      // Normal loading on initial session change
      fetchActions(selectedSessionId, false);
    }
  }, [selectedSessionId]);

  // Gentle fallback background polling (silent, non-destructive to scroll position)
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedSessionId) {
        fetchActions(selectedSessionId, true);
      }
      fetchSessions(true);
    }, 12000);
    return () => clearInterval(interval);
  }, [selectedSessionId]);

  const handleSyncCopilot = async () => {
    setIsSyncingCopilot(true);
    try {
      await fetch('/api/copilot/sync', { method: 'POST' });
      await fetchSessions(true);
      if (selectedSessionId) {
        await fetchActions(selectedSessionId, true);
      }
    } catch {}
    setTimeout(() => setIsSyncingCopilot(false), 600);
  };

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

            {/* Active AI Client Badge */}
            {sessions.length > 0 && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-800/50 text-xs font-mono">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span className="text-cyan-300 truncate max-w-[200px]">
                  {selectedSession?.client_name || sessions[0].client_name}
                </span>
              </div>
            )}
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
            <button
              type="button"
              onClick={() => setActiveTab('clients')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'clients'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#121824]'
              }`}
            >
              <Cpu className="w-4 h-4" /> AI Client Connect
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
            {/* Architecture Explainer Card */}
            <div className="p-4 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start md:items-center gap-3">
                <div className="p-2.5 rounded-xl bg-blue-500/10 text-cyan-400 shrink-0 mt-0.5 md:mt-0">
                  <Cpu className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-200">
                      AI Client Guard Mode:
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded-full font-mono bg-emerald-950/60 border border-emerald-800 text-emerald-400">
                      {selectedSession?.client_name || 'VS Code + GitHub Copilot'} Active
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    SafeAI is an action firewall. You chat with your AI inside <strong>VS Code Copilot, Claude Desktop, or Cursor</strong> as usual. SafeAI automatically intercepts, screens, and pauses <strong>executable tools</strong> (shell commands, file reads/writes) whenever risk exceeds your threshold.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('clients')}
                className="shrink-0 text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] hover:border-cyan-500/50 transition-colors self-start md:self-auto"
              >
                Connect Clients &rarr;
              </button>
            </div>

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
                <button
                  type="button"
                  onClick={handleSyncCopilot}
                  disabled={isSyncingCopilot}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-950/40 hover:bg-purple-900/50 border border-purple-800/50 text-purple-300 text-xs font-semibold transition-colors"
                  title="Scan & Sync VS Code Copilot Chat History"
                >
                  <MessageSquare className={`w-3.5 h-3.5 ${isSyncingCopilot ? 'animate-pulse text-cyan-300' : ''}`} />
                  {isSyncingCopilot ? 'Syncing...' : 'Sync Copilot Chat'}
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
                  className="px-3 py-1.5 text-xs rounded-xl bg-[#121824] border border-[#1f293d] text-slate-200 font-medium focus:outline-none focus:border-blue-500 max-w-sm truncate"
                >
                  {sessions.length === 0 ? (
                    <option value="">No sessions recorded</option>
                  ) : (
                    sessions.map((s) => {
                      const startDate = new Date(s.started_at);
                      const dateStr = startDate.toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                      });
                      const timeStr = startDate.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      });

                      const sessionLabel = s.title
                        ? `${s.title} (${dateStr}, ${timeStr})`
                        : `${s.client_name} (${dateStr}, ${timeStr})`;

                      return (
                        <option key={s.id} value={s.id}>
                          {sessionLabel}
                        </option>
                      );
                    })
                  )}
                </select>
              </div>
            </div>

            {/* Timeline Stream */}
            <SessionTimeline
              actions={actions}
              isLoading={isLoadingActions}
              session={selectedSession}
            />
          </div>
        )}

        {/* Tab 2: Policy Settings */}
        {activeTab === 'settings' && (
          <SettingsPanel
            settings={settings}
            onUpdateSettings={handleUpdateSettings}
            onNavigateToClients={() => setActiveTab('clients')}
          />
        )}

        {/* Tab 3: AI Client Connect Guides */}
        {activeTab === 'clients' && (
          <ClientConfigPanel />
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
