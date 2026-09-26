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
  // Sub-tabs: 'all' (default), 'interceptions', or 'chat'
  const [activeSubTab, setActiveSubTab] = useState<'interceptions' | 'chat' | 'all'>('all');

  const chatTurns = useMemo(() => {
    return actions.filter((a) => a.tool_name === 'copilot_chat');
  }, [actions]);

  const toolInterceptions = useMemo(() => {
    return actions.filter((a) => a.tool_name !== 'copilot_chat');
  }, [actions]);

  // If there are zero tool calls but there ARE chat turns, automatically suggest chat history or default to chat
  const displayedActions = useMemo(() => {
    if (activeSubTab === 'interceptions') {
      return toolInterceptions;
    }
    if (activeSubTab === 'chat') {
      return chatTurns;
    }
    return actions;
  }, [activeSubTab, toolInterceptions, chatTurns, actions]);

  const totalActions = session ? session.total_actions : actions.length;
  const blockedActions = session
    ? session.blocked_actions
    : actions.filter((a) => a.risk_score >= 50 || a.status === 'REJECTED').length;

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

      {/* Interceptions vs Chat History Tabs Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
        <div className="flex items-center gap-2 bg-[#121824] p-1.5 rounded-2xl border border-[#1f293d]">
          {/* Sub-tab 1: Interceptions & Tool Calls (Default) */}
          <button
            type="button"
            onClick={() => setActiveSubTab('interceptions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'interceptions'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            Interceptions & Tool Calls
            <span
              className={`text-[10px] px-2 py-0.2 rounded-full font-mono ${
                activeSubTab === 'interceptions'
                  ? 'bg-blue-800 text-blue-100'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {toolInterceptions.length}
            </span>
          </button>

          {/* Sub-tab 2: Full Chat History */}
          <button
            type="button"
            onClick={() => setActiveSubTab('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'chat'
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Full Chat History
            <span
              className={`text-[10px] px-2 py-0.2 rounded-full font-mono ${
                activeSubTab === 'chat'
                  ? 'bg-purple-800 text-purple-100'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {chatTurns.length}
            </span>
          </button>

          {/* Sub-tab 3: All Interactions */}
          <button
            type="button"
            onClick={() => setActiveSubTab('all')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeSubTab === 'all'
                ? 'bg-slate-700 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            All Activity
            <span
              className={`text-[10px] px-2 py-0.2 rounded-full font-mono ${
                activeSubTab === 'all'
                  ? 'bg-slate-800 text-slate-200'
                  : 'bg-[#0a0d14] text-slate-400 border border-[#1f293d]'
              }`}
            >
              {actions.length}
            </span>
          </button>
        </div>

        <span className="text-xs text-slate-400 font-mono">
          Showing {displayedActions.length} of {actions.length} records
        </span>
      </div>

      {/* Sub-Tab 1 Empty State: If no tool interceptions but there IS chat history */}
      {activeSubTab === 'interceptions' && toolInterceptions.length === 0 && (
        <div className="p-8 rounded-2xl bg-[#121824] border border-[#1f293d] space-y-4 text-center">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              No High-Risk Tool Executions Intercepted in this Session
            </h3>
            <p className="text-xs text-slate-400 max-w-lg mx-auto mt-1 leading-relaxed">
              SafeAI only intercepts and screens <strong>executable tools</strong> (shell commands, file modifications, sensitive API calls). This session consists of conversational dialogue with zero dangerous tool calls held.
            </p>
          </div>

          {chatTurns.length > 0 && (
            <button
              type="button"
              onClick={() => setActiveSubTab('chat')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition-all shadow-md shadow-purple-600/20"
            >
              <MessageSquare className="w-4 h-4" />
              View Full Chat History ({chatTurns.length} turns) &rarr;
            </button>
          )}
        </div>
      )}

      {/* Timeline of displayed actions */}
      {(activeSubTab !== 'interceptions' || toolInterceptions.length > 0) && (
        <SessionTimeline
          actions={displayedActions}
          isLoading={isLoadingActions}
          session={session}
        />
      )}
    </div>
  );
};
