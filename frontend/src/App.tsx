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
import { LiveActivityView } from './components/LiveActivityView';
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
  const [liveActions, setLiveActions] = useState<ActionLog[]>([]);
  const [isLoadingLiveActions, setIsLoadingLiveActions] = useState<boolean>(false);

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
        const activeData = data.filter((s: SessionRecord) => (s.total_actions || 0) > 0);
        setSessions((prev) => {
          if (
            prev.length === activeData.length &&
            prev[0]?.id === activeData[0]?.id &&
            prev[0]?.total_actions === activeData[0]?.total_actions &&
            prev[0]?.title === activeData[0]?.title
          ) {
            return prev;
          }
          return activeData;
        });
        if (activeData.length > 0 && (!selectedSessionId || !activeData.some((s) => s.id === selectedSessionId))) {
          setSelectedSessionId(activeData[0].id);
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

  // Fetch latest 50 actions across ALL sessions for the Live Activity stream
  const fetchLiveActions = async (silent = false) => {
    if (!silent) {
      setIsLoadingLiveActions(true);
    }
    try {
      const res = await fetch('/api/actions?limit=50');
      if (res.ok) {
        const data: ActionLog[] = await res.json();
        setLiveActions((prev) => {
          if (
            prev.length === data.length &&
            prev[0]?.id === data[0]?.id &&
            prev[0]?.status === data[0]?.status &&
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
        setIsLoadingLiveActions(false);
      }
    }
  };

  // WebSocket action listener for instant live events without page reloads
  const handleActionLogged = useCallback((evt: any) => {
    fetchLiveActions(true);
    if (selectedSessionId && (!evt.sessionId || evt.sessionId === selectedSessionId)) {
      fetchActions(selectedSessionId, true);
    }
    fetchSessions(true);
  }, [selectedSessionId]);

  const handleDatabaseCleaned = useCallback(() => {
    setSelectedSessionId(null);
    setActions([]);
    setLiveActions([]);
    setSessions([]);
    setIsViewingDetail(false);
    fetchSessions();
    fetchLiveActions();
  }, []);

  const { isConnected, pendingApprovals, submitDecision } = useSafeAIWebSocket({
    onActionLogged: handleActionLogged,
    onDatabaseCleaned: handleDatabaseCleaned,
  });

  useEffect(() => {
    fetchSettings();
    fetchSessions();
    fetchLiveActions();
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
      fetchLiveActions(true);
    }, 15000);
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

  const selectedSession = sessions.find((s) => s.id === selectedSessionId) || (sessions.length > 0 ? sessions[0] : null);

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-[#0d121d]/90 backdrop-blur-md border-b border-[#1f293d]">
        <div className="max-w-[1440px] mx-auto px-6 h-16 flex items-center justify-between gap-6">
          <div className="flex items-center gap-3 sm:gap-3.5 flex-shrink-0">
            {/* SafeAI Logo & Title Button (Returns to Sessions & History Initial Page) */}
            <button
              type="button"
              onClick={() => {
                setActiveTab('sessions');
                setIsViewingDetail(false);
              }}
              className="flex items-center gap-2.5 text-left group transition-all hover:opacity-90 focus:outline-none flex-shrink-0 cursor-pointer"
              title="Return to Sessions & History"
            >
              <div className="p-2 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-base tracking-tight text-white group-hover:text-blue-200 transition-colors">SafeAI</h1>
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400">
                    CORE GATEWAY
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-mono">Agent Security & Explainer Governance</p>
              </div>
            </button>

            {/* Connection Status Badge (moved closer to logo on the left) */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-[#121824] border border-[#1f293d] text-xs font-mono flex-shrink-0">
              <span
                className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`}
              />
              <span className="text-slate-300 whitespace-nowrap">
                {isConnected ? 'LIVE WEBSOCKET' : 'CONNECTING...'}
              </span>
            </div>

            {/* Active AI Client Badge (with expanded width and no shrinkage) */}
            {sessions.length > 0 && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-800/50 text-xs font-mono flex-shrink-0">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                <span className="text-cyan-300 truncate max-w-[280px] font-medium">
                  {selectedSession?.client_name || 'VS Code + GitHub Copilot'}
                </span>
              </div>
            )}
          </div>

          {/* Main Navigation Tabs with guaranteed left margin */}
          <div className="flex items-center gap-2 flex-shrink-0 ml-6">
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
                fetchLiveActions(true);
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
              <Sliders className="w-4 h-4" /> Settings
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
              />
            ) : (
              <SessionsPage
                sessions={sessions}
                onSelectSession={(id) => {
                  setSelectedSessionId(id);
                  setIsViewingDetail(true);
                }}
              />
            )}
          </>
        )}

        {/* Tab 2: Live Activity / Active Monitor (Last 50 Activities across ALL Sessions) */}
        {activeTab === 'live' && (
          <LiveActivityView
            actions={liveActions}
            sessions={sessions}
            isLoading={isLoadingLiveActions}
            onRefresh={() => {
              fetchLiveActions();
              fetchSessions(true);
            }}
            onSelectSession={(sessionId) => {
              setSelectedSessionId(sessionId);
              setIsViewingDetail(true);
              setActiveTab('sessions');
            }}
            onBrowseSessions={() => {
              setActiveTab('sessions');
              setIsViewingDetail(false);
            }}
          />
        )}

        {/* Tab 3: Security & Governance Settings */}
        {activeTab === 'settings' && (
          <SettingsPanel
            settings={settings}
            onUpdateSettings={handleUpdateSettings}
            onDatabaseCleaned={handleDatabaseCleaned}
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
