import React, { useState, useMemo } from 'react';
import {
  Activity,
  ShieldCheck,
  ShieldAlert,
  Terminal,
  Layers,
  RefreshCw,
  Cpu,
  Download,
  Filter,
} from 'lucide-react';
import { ActionLog, SessionRecord } from '../types';
import { SessionTimeline } from './SessionTimeline';

interface LiveActivityViewProps {
  actions: ActionLog[];
  sessions: SessionRecord[];
  isLoading: boolean;
  onRefresh: () => void;
  onSelectSession: (sessionId: string) => void;
  onBrowseSessions: () => void;
}

export const LiveActivityView: React.FC<LiveActivityViewProps> = ({
  actions,
  sessions,
  isLoading,
  onRefresh,
  onSelectSession,
  onBrowseSessions,
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'all' | 'blocked' | 'safe'>('all');
  const [sessionFilter, setSessionFilter] = useState<string>('all');

  const isBlockedOrFlagged = (a: ActionLog) =>
    a.risk_score >= 50 || a.status === 'REJECTED' || a.status === 'TIMED_OUT';

  const totalInvocations = actions.length;
  const blockedCount = useMemo(() => actions.filter(isBlockedOrFlagged).length, [actions]);
  const safeCount = useMemo(() => actions.filter((a) => !isBlockedOrFlagged(a)).length, [actions]);
  const safePercentage =
    totalInvocations > 0 ? Math.round(((totalInvocations - blockedCount) / totalInvocations) * 100) : 100;

  // Distinct sessions represented in current actions
  const sessionStats = useMemo(() => {
    const map = new Map<string, number>();
    for (const a of actions) {
      if (a.session_id) {
        map.set(a.session_id, (map.get(a.session_id) || 0) + 1);
      }
    }
    return map;
  }, [actions]);

  // Session options for filter dropdown
  const sessionOptions = useMemo(() => {
    const list: { id: string; title: string; count: number }[] = [];
    sessionStats.forEach((count, sid) => {
      const s = sessions.find((item) => item.id === sid);
      const title = s?.title || s?.client_name || sid;
      list.push({ id: sid, title, count });
    });
    // Sort by count descending
    return list.sort((a, b) => b.count - a.count);
  }, [sessionStats, sessions]);

  // Filter actions by session filter and subtab
  const displayedActions = useMemo(() => {
    let result = actions;

    if (sessionFilter !== 'all') {
      result = result.filter((a) => a.session_id === sessionFilter);
    }

    if (activeSubTab === 'blocked') {
      result = result.filter(isBlockedOrFlagged);
    } else if (activeSubTab === 'safe') {
      result = result.filter((a) => !isBlockedOrFlagged(a));
    }

    return result;
  }, [actions, sessionFilter, activeSubTab]);

  const handleExport = () => {
    const url = sessionFilter !== 'all' ? `/api/logs/export?session_id=${sessionFilter}` : '/api/logs/export';
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Live Gateway Monitor Header Card */}
      <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-cyan-400">
            <Activity className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono text-slate-400">Active Live Gateway Monitor</span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                LIVE STREAM · LAST 50 ACTIVITIES
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-100 mt-1">
              Live Cross-Session Activity Feed
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Real-time stream of the last 50 tool invocations, security checks, and approvals across all sessions.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start md:self-center">
          <button
            type="button"
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] hover:border-slate-600 text-slate-300 text-xs font-semibold transition-colors"
            title="Refresh Live Activity"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={onBrowseSessions}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] hover:border-cyan-500/50 text-cyan-400 text-xs font-semibold transition-colors"
          >
            <Layers className="w-3.5 h-3.5" /> Sessions Directory &rarr;
          </button>
        </div>
      </div>

      {/* Summary Metrics across the 50 activities */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Invocations */}
        <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium">Total Invocations</span>
            <h4 className="text-2xl font-bold font-mono text-slate-100 mt-1">{totalInvocations}</h4>
            <span className="text-[10px] text-slate-500 font-mono">Last 50 recorded</span>
          </div>
          <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        {/* Blocked / Flagged */}
        <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium">Blocked / Flagged</span>
            <h4 className="text-2xl font-bold font-mono text-red-400 mt-1">{blockedCount}</h4>
            <span className="text-[10px] text-slate-500 font-mono">Risk &ge; 50 or denied</span>
          </div>
          <div className="p-3 rounded-xl bg-red-500/10 text-red-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>

        {/* Safe Clearance Rate */}
        <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium">Safe Clearance Rate</span>
            <h4 className="text-2xl font-bold font-mono text-emerald-400 mt-1">{safePercentage}%</h4>
            <span className="text-[10px] text-slate-500 font-mono">{safeCount} safe calls</span>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>

        {/* Active Sessions Represented */}
        <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium">Active Sessions</span>
            <h4 className="text-2xl font-bold font-mono text-cyan-400 mt-1">{sessionStats.size}</h4>
            <span className="text-[10px] text-slate-500 font-mono">in this window</span>
          </div>
          <div className="p-3 rounded-xl bg-cyan-500/10 text-cyan-400">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        {/* Audit Trail Export */}
        <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-medium">Audit Trail (DLP Safe)</span>
            <button
              type="button"
              onClick={handleExport}
              className="mt-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1f293d] hover:bg-blue-600 text-xs font-semibold text-slate-200 hover:text-white transition-all shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              Export JSON
            </button>
          </div>
          <div className="p-3 rounded-xl bg-slate-800 text-slate-400">
            <Cpu className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter Header: Sub-tabs and Session Filter */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2 bg-[#121824] p-1.5 rounded-2xl border border-[#1f293d] flex-wrap">
          {/* Sub-tab 1: Interceptions & Tool Calls */}
          <button
            type="button"
            onClick={() => setActiveSubTab('all')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'all'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            Interceptions & Tool Calls
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                activeSubTab === 'all'
                  ? 'bg-blue-800 text-blue-100'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {actions.length}
            </span>
          </button>

          {/* Sub-tab 2: Blocked / Flagged */}
          <button
            type="button"
            onClick={() => setActiveSubTab('blocked')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'blocked'
                ? 'bg-red-600 text-white shadow-md shadow-red-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            Blocked / Flagged
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                activeSubTab === 'blocked'
                  ? 'bg-red-800 text-red-100'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {blockedCount}
            </span>
          </button>

          {/* Sub-tab 3: Safe Calls */}
          <button
            type="button"
            onClick={() => setActiveSubTab('safe')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'safe'
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Safe Calls
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${
                activeSubTab === 'safe'
                  ? 'bg-emerald-800 text-emerald-100'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {safeCount}
            </span>
          </button>
        </div>

        {/* Right side: Session filter dropdown & record count */}
        <div className="flex items-center gap-3 flex-wrap">
          {sessionOptions.length > 1 && (
            <div className="flex items-center gap-2 bg-[#121824] px-3 py-1.5 rounded-xl border border-[#1f293d]">
              <Filter className="w-3.5 h-3.5 text-cyan-400" />
              <select
                value={sessionFilter}
                onChange={(e) => setSessionFilter(e.target.value)}
                className="bg-transparent text-xs text-slate-200 font-mono outline-none cursor-pointer max-w-[240px]"
              >
                <option value="all" className="bg-[#121824] text-slate-200">
                  All Sessions ({actions.length})
                </option>
                {sessionOptions.map((opt) => (
                  <option key={opt.id} value={opt.id} className="bg-[#121824] text-slate-200">
                    {opt.title} ({opt.count})
                  </option>
                ))}
              </select>
            </div>
          )}

          <span className="text-xs text-slate-400 font-mono">
            Showing {displayedActions.length} of {actions.length} records (All Sessions)
          </span>
        </div>
      </div>

      {/* Empty State for Blocked / Flagged */}
      {activeSubTab === 'blocked' && displayedActions.length === 0 && (
        <div className="p-8 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-3 text-center">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              No Blocked or Flagged Invocations
            </h3>
            <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1 leading-relaxed">
              All tool calls across recent sessions were evaluated as safe and passed governance policy.
            </p>
          </div>
        </div>
      )}

      {/* Empty State for Safe Calls */}
      {activeSubTab === 'safe' && displayedActions.length === 0 && (
        <div className="p-8 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-3 text-center">
          <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              No Safe Calls in this View
            </h3>
            <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1 leading-relaxed">
              All calls recorded in this view were flagged for human-in-the-loop review.
            </p>
          </div>
        </div>
      )}

      {/* Activity Timeline across all sessions */}
      {displayedActions.length > 0 && (
        <SessionTimeline
          actions={displayedActions}
          isLoading={isLoading}
          sessions={sessions}
          showSessionBadge={true}
          onSelectSession={onSelectSession}
        />
      )}

      {actions.length === 0 && !isLoading && (
        <SessionTimeline
          actions={[]}
          isLoading={false}
          session={null}
        />
      )}
    </div>
  );
};

export default LiveActivityView;
