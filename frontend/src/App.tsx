import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  Activity,
  Sliders,
  Radio,
  Cpu,
  Layers,
} from 'lucide-react';
import { useSafeAIWebSocket } from './hooks/useSafeAIWebSocket';
import { ApprovalModal } from './components/ApprovalModal';
import { SessionsPage } from './components/SessionsPage';
import { SessionDetailView } from './components/SessionDetailView';
import { SettingsPanel } from './components/SettingsPanel';
import { ClientConfigPanel } from './components/ClientConfigPanel';
import { ActionLog, SafeAISettings, SessionRecord } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'sessions' | 'live' | 'settings' | 'clients'>('sessions');
  const [isViewingDetail, setIsViewingDetail] = useState<boolean>(false);
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

  // Fetch recent sessions (silent = true prevents unnecessary re-renders)
  const fetchSessions = async (silent = false) => {
    try {
      const res = await fetch('/api/sessions?limit=100');
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

  // WebSocket action listener for instant live events without page reloads
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
      fetchActions(selectedSessionId, false);
    }
  }, [selectedSessionId]);

  // Gentle fallback background polling (silent, non-destructive)
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedSessionId) {
        fetchActions(selectedSessionId, true);
      }
      fetchSessions(true);
    }, 15000);
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

  const selectedSession = sessions.find((s) => s.id === selectedSessionId) || (sessions.length > 0 ? sessions[0] : null);

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
                  {selectedSession?.client_name || 'VS Code + GitHub Copilot'}
                </span>
              </div>
            )}
          </div>

          {/* Main Navigation Tabs */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveTab('sessions');
                setIsViewingDetail(false);
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'sessions'
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#121824]'
              }`}
            >
              <Layers className="w-4 h-4" /> Sessions & History
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('live');
                if (sessions.length > 0 && !selectedSessionId) {
                  setSelectedSessionId(sessions[0].id);
                }
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'live'
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

        {/* Tab 1: Sessions Explorer & History (Paginated, Searchable, Ordered Newest-to-Oldest) */}
        {activeTab === 'sessions' && (
          <>
            {isViewingDetail && selectedSession ? (
              <SessionDetailView
                session={selectedSession}
                actions={actions}
                isLoadingActions={isLoadingActions}
                onBack={() => setIsViewingDetail(false)}
                onRefresh={() => {
                  fetchSessions(true);
                  if (selectedSessionId) fetchActions(selectedSessionId, true);
                }}
                onSyncCopilot={handleSyncCopilot}
                isSyncingCopilot={isSyncingCopilot}
              />
            ) : (
              <SessionsPage
                sessions={sessions}
                onSelectSession={(id) => {
                  setSelectedSessionId(id);
                  setIsViewingDetail(true);
                }}
                onSyncCopilot={handleSyncCopilot}
                isSyncingCopilot={isSyncingCopilot}
              />
            )}
          </>
        )}

        {/* Tab 2: Live Activity / Active Monitor */}
        {activeTab === 'live' && (
          <div className="space-y-6">
            {/* Live Gateway Header Card */}
            <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
              <div className="flex items-center gap-3.5">
                <div className="p-3 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-cyan-400">
                  <Activity className="w-6 h-6 animate-pulse" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">Active Live Gateway Monitor</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  </div>
                  <h3 className="text-base font-bold text-slate-100 mt-0.5">
                    {selectedSession?.title || 'Monitoring Connected AI Agents'}
                  </h3>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab('sessions');
                    setIsViewingDetail(false);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] hover:border-cyan-500/50 text-cyan-400 text-xs font-semibold transition-colors"
                >
                  <Layers className="w-3.5 h-3.5" /> Browse All Sessions Directory &rarr;
                </button>
              </div>
            </div>

            {selectedSession && (
              <SessionDetailView
                session={selectedSession}
                actions={actions}
                isLoadingActions={isLoadingActions}
                onBack={() => {
                  setActiveTab('sessions');
                  setIsViewingDetail(false);
                }}
                onRefresh={() => {
                  fetchSessions(true);
                  if (selectedSessionId) fetchActions(selectedSessionId, true);
                }}
                onSyncCopilot={handleSyncCopilot}
                isSyncingCopilot={isSyncingCopilot}
              />
            )}
          </div>
        )}

        {/* Tab 3: Security & Governance Settings */}
        {activeTab === 'settings' && (
          <SettingsPanel
            settings={settings}
            onUpdateSettings={handleUpdateSettings}
          />
        )}

        {/* Tab 4: AI Client Connect Hub */}
        {activeTab === 'clients' && <ClientConfigPanel />}
      </main>

      {/* Human-in-the-Loop Modal for Pending Approvals */}
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
