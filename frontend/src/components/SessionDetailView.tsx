import React, { useState, useMemo } from 'react';
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  Terminal,
  MessageSquare,
  Cpu,
  Layers,
  Clock,
  Calendar,
  Download,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { ActionLog, SessionRecord } from '../types';
import { SessionSummary } from './SessionSummary';
import { SessionTimeline } from './SessionTimeline';

interface SessionDetailViewProps {
  session: SessionRecord;
  actions: ActionLog[];
  isLoadingActions: boolean;
  onBack: () => void;
  onRefresh: () => void;
}

export const SessionDetailView: React.FC<SessionDetailViewProps> = ({
  session,
  actions,
  isLoadingActions,
  onBack,
  onRefresh,
}) => {
  // Sub-tabs: 'all' (Interceptions & Tool Calls), 'blocked' (Blocked / Flagged), 'safe' (Safe Calls)
  const [activeSubTab, setActiveSubTab] = useState<'all' | 'blocked' | 'safe'>('all');

  const isBlockedOrFlagged = (a: ActionLog) =>
    a.risk_score >= 50 || a.status === 'REJECTED' || a.status === 'TIMED_OUT';

  const blockedOrFlaggedActions = useMemo(() => {
    return actions.filter(isBlockedOrFlagged);
  }, [actions]);

  const safeActions = useMemo(() => {
    return actions.filter((a) => !isBlockedOrFlagged(a));
  }, [actions]);

  const displayedActions = useMemo(() => {
    if (activeSubTab === 'blocked') {
      return blockedOrFlaggedActions;
    }
    if (activeSubTab === 'safe') {
      return safeActions;
    }
    return actions;
  }, [activeSubTab, blockedOrFlaggedActions, safeActions, actions]);

  const totalActions = actions.length > 0 ? actions.length : (session?.total_actions || 0);
  const blockedActions =
    actions.length > 0 ? blockedOrFlaggedActions.length : (session?.blocked_actions || 0);

  const isCopilot = (session.client_name || '').includes('Copilot');
  const formattedDate = new Date(session.started_at).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Session Header */}
      <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-cyan-300 transition-colors self-start group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            Back to All Sessions
          </button>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <button
              type="button"
              onClick={onRefresh}
              className="p-2 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-400 hover:text-slate-200 transition-colors"
              title="Refresh Session"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="border-t border-[#1f293d] pt-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium ${
                  isCopilot
                    ? 'bg-purple-950/60 text-purple-300 border border-purple-800/60'
                    : 'bg-cyan-950/60 text-cyan-300 border border-cyan-800/60'
                }`}
              >
                {isCopilot ? (
                  <MessageSquare className="w-3 h-3 text-purple-400" />
                ) : (
                  <Cpu className="w-3 h-3 text-cyan-400" />
                )}
                {session.client_name}
              </span>
              <span className="text-xs text-slate-500 font-mono">ID: {session.id}</span>
            </div>

            <h1 className="text-xl font-bold text-slate-100 mt-2 leading-snug">
              {session.title || `${session.client_name} Session`}
            </h1>
            <p className="text-xs text-slate-400 font-mono mt-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-500" /> Started: {formattedDate}
            </p>
          </div>
        </div>
      </div>

      {/* Session Summary Cards */}
      <SessionSummary
        session={session}
        totalActions={totalActions}
        blockedActions={blockedActions}
      />

      {/* Tab Filter Header: Interceptions & Tool Calls | Blocked / Flagged | Safe Calls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2 bg-[#121824] p-1.5 rounded-2xl border border-[#1f293d]">
          {/* Sub-tab 1: Interceptions & Tool Calls (All Calls) */}
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
              {blockedOrFlaggedActions.length}
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
              {safeActions.length}
            </span>
          </button>
        </div>

        <span className="text-xs text-slate-400 font-mono">
          Showing {displayedActions.length} of {actions.length} records
        </span>
      </div>

      {/* Empty State for Blocked / Flagged */}
      {activeSubTab === 'blocked' && blockedOrFlaggedActions.length === 0 && (
        <div className="p-8 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-3 text-center">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              No Blocked or Flagged Invocations
            </h3>
            <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1 leading-relaxed">
              All tool calls and executions in this session were verified safe and executed without policy violations.
            </p>
          </div>
        </div>
      )}

      {/* Empty State for Safe Calls */}
      {activeSubTab === 'safe' && safeActions.length === 0 && (
        <div className="p-8 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-3 text-center">
          <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              No Safe Calls in this View
            </h3>
            <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1 leading-relaxed">
              All calls recorded in this session were flagged or held for human-in-the-loop review.
            </p>
          </div>
        </div>
      )}

      {/* Timeline of displayed actions */}
      {((activeSubTab === 'all' && actions.length > 0) ||
        (activeSubTab === 'blocked' && blockedOrFlaggedActions.length > 0) ||
        (activeSubTab === 'safe' && safeActions.length > 0) ||
        actions.length === 0) && (
        <SessionTimeline
          actions={displayedActions}
          isLoading={isLoadingActions}
          session={session}
        />
      )}
    </div>
  );
};
