import React from 'react';
import { ActionLog, SessionRecord } from '../types';
import { ShieldCheck, ShieldAlert, Clock, CheckCircle2, XCircle, Terminal, FileText, Zap, Sparkles, MessageSquare, User, Bot, RefreshCw, Layers } from 'lucide-react';

interface SessionTimelineProps {
  actions: ActionLog[];
  isLoading?: boolean;
  session?: SessionRecord | null;
  sessions?: SessionRecord[];
  showSessionBadge?: boolean;
  onSelectSession?: (sessionId: string) => void;
}

export const SessionTimeline: React.FC<SessionTimelineProps> = ({
  actions,
  isLoading,
  session,
  sessions,
  showSessionBadge = false,
  onSelectSession,
}) => {
  // Never unmount existing timeline when refreshing in the background
  if (isLoading && actions.length === 0) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-500 font-mono text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
        Loading session activity...
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className="p-8 text-slate-400 bg-[#121824] rounded-2xl border border-[#1f293d] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1f293d] pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-cyan-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                Agent Guard Active — Standing By
              </h4>
              <p className="text-xs text-slate-400">
                Connected to{' '}
                <strong className="text-slate-200">
                  {session?.client_name || 'VS Code + GitHub Copilot'}
                </strong>
              </p>
            </div>
          </div>

          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 self-start sm:self-center">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Listening on MCP SSE
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          <div className="p-4 rounded-xl bg-[#0a0d14] border border-[#1f293d] space-y-2">
            <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-amber-400" /> Why only tool interceptions appear:
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              In <strong>Model Context Protocol (MCP)</strong> mode, general text conversation happens inside GitHub Copilot. SafeAI acts as a <strong>security firewall & explainer</strong> that intercepts and guards <strong>executable tools</strong> (running terminal commands, reading or writing files, calling external APIs).
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[#0a0d14] border border-[#1f293d] space-y-2">
            <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-cyan-400" /> How to test it right now in VS Code:
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Open <strong>Copilot Chat</strong> (in Agent mode or with SafeAI enabled) and prompt:
            </p>
            <div className="p-2 rounded-lg bg-[#121824] border border-[#1f293d] text-cyan-300 font-mono text-[11px]">
              &quot;Run git status using bash&quot; or &quot;Read the README.md file&quot;
            </div>
            <p className="text-[11px] text-slate-500">
              Copilot will invoke the tool, and SafeAI will instantly intercept it here, translate the action into plain language, evaluate security risk, and request approval if risky!
            </p>
          </div>
        </div>
      </div>
    );
  }

  const getStatusBadge = (status: ActionLog['status']) => {
    switch (status) {
      case 'AUTO_APPROVED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/40 text-emerald-400 border border-emerald-800/40">
            <CheckCircle2 className="w-3 h-3" /> Auto Approved
          </span>
        );
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-950/40 text-blue-400 border border-blue-800/40">
            <ShieldCheck className="w-3 h-3" /> User Approved
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-950/40 text-red-400 border border-red-800/40">
            <XCircle className="w-3 h-3" /> Denied
          </span>
        );
      case 'TIMED_OUT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/40 text-amber-400 border border-amber-800/40">
            <Clock className="w-3 h-3" /> Timed Out
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
            Pending
          </span>
        );
    }
  };

  const getRiskScoreColor = (score: number) => {
    if (score >= 80) return 'text-red-400 bg-red-500/10 border-red-500/30';
    if (score >= 50) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
  };

  return (
    <div className="space-y-4">
      {actions.map((act) => {
        let factors: string[] = [];
        try {
          factors = typeof act.risk_factors === 'string' ? JSON.parse(act.risk_factors) : act.risk_factors || [];
        } catch {
          factors = [];
        }

        const actSession =
          sessions?.find((s) => s.id === act.session_id) ||
          (session?.id === act.session_id ? session : null);

        const isCopilotChat = act.tool_name === 'copilot_chat';
        let chatData: { prompt?: string; response?: string; model?: string } = {};
        if (isCopilotChat) {
          try {
            chatData = JSON.parse(act.raw_payload);
          } catch {}
        }

        if (isCopilotChat) {
          return (
            <div
              key={act.id}
              className="p-5 rounded-2xl bg-[#121824] border border-blue-900/30 hover:border-blue-800/50 transition-all space-y-3.5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
                    <MessageSquare className="w-4 h-4" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-slate-100">Copilot Conversation Turn</span>
                      {chatData.model && (
                        <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-purple-950/50 border border-purple-800 text-purple-300">
                          {chatData.model.replace('copilot/', '')}
                        </span>
                      )}
                      {showSessionBadge && actSession && (
                        <button
                          type="button"
                          onClick={() => onSelectSession?.(actSession.id)}
                          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] hover:border-purple-500/50 text-slate-300 hover:text-purple-300 text-xs font-mono transition-all group"
                          title={`View session: ${actSession.title || actSession.id}`}
                        >
                          <Layers className="w-3 h-3 text-purple-400 group-hover:scale-110 transition-transform" />
                          <span className="truncate max-w-[200px]">{actSession.title || actSession.id}</span>
                          <span className="text-[10px] text-purple-400">&rarr;</span>
                        </button>
                      )}
                    </div>
                    <span className="text-xs text-slate-500 font-mono">
                      {new Date(act.timestamp).toLocaleTimeString()} · Automated Local Sync
                    </span>
                  </div>
                </div>

                <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 font-mono">
                  Copilot Model
                </span>
              </div>

              {/* User Prompt */}
              {chatData.prompt && (
                <div className="p-3.5 rounded-xl bg-blue-950/25 border border-blue-900/40 space-y-1">
                  <div className="text-[11px] font-semibold text-cyan-300 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5" /> User:
                  </div>
                  <div className="text-xs text-slate-200 leading-relaxed font-sans font-medium">
                    {chatData.prompt}
                  </div>
                </div>
              )}

              {/* Copilot Response */}
              {act.execution_result && (
                <div className="p-3.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] space-y-1.5">
                  <div className="text-[11px] font-semibold text-purple-300 flex items-center gap-1.5">
                    <Bot className="w-3.5 h-3.5" /> GitHub Copilot Response:
                  </div>
                  <div className="text-xs text-slate-300 leading-relaxed font-sans whitespace-pre-wrap max-h-72 overflow-y-auto">
                    {act.execution_result}
                  </div>
                </div>
              )}
            </div>
          );
        }

        return (
          <div
            key={act.id}
            className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] hover:border-[#2a3854] transition-all space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="p-2 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-blue-400">
                  <Terminal className="w-4 h-4" />
                </span>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-slate-100">{act.tool_name}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-md border font-mono font-medium ${getRiskScoreColor(
                        act.risk_score
                      )}`}
                    >
                      Risk {act.risk_score}/100
                    </span>
                    {showSessionBadge && actSession && (
                      <button
                        type="button"
                        onClick={() => onSelectSession?.(actSession.id)}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 text-xs font-mono transition-all group"
                        title={`View session: ${actSession.title || actSession.id}`}
                      >
                        <Layers className="w-3 h-3 text-cyan-400 group-hover:scale-110 transition-transform" />
                        <span className="truncate max-w-[200px]">{actSession.title || actSession.id}</span>
                        <span className="text-[10px] text-cyan-400">&rarr;</span>
                      </button>
                    )}
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    {new Date(act.timestamp).toLocaleTimeString()} · ID: {act.id}
                  </span>
                </div>
              </div>

              <div>{getStatusBadge(act.status)}</div>
            </div>

            {/* Plain Language Explanation */}
            <div className="p-3 rounded-xl bg-[#0a0d14]/70 border border-[#1f293d]/60 text-xs leading-relaxed text-slate-300">
              <span className="text-slate-500 font-medium">Summary: </span>
              {act.plain_language_explanation}
            </div>

            {/* Risk factors tags with CIA categorization */}
            {factors.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {factors.map((f, i) => {
                  if (typeof f === 'string' && f.startsWith('[Integrity]')) {
                    return (
                      <span
                        key={i}
                        className="text-[11px] px-2 py-0.5 rounded bg-rose-950/40 border border-rose-800/50 text-rose-300 font-mono inline-flex items-center gap-1"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                        {f}
                      </span>
                    );
                  }
                  if (typeof f === 'string' && f.startsWith('[Confidentiality]')) {
                    return (
                      <span
                        key={i}
                        className="text-[11px] px-2 py-0.5 rounded bg-purple-950/40 border border-purple-800/50 text-purple-300 font-mono inline-flex items-center gap-1"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
                        {f}
                      </span>
                    );
                  }
                  if (typeof f === 'string' && f.startsWith('[Availability]')) {
                    return (
                      <span
                        key={i}
                        className="text-[11px] px-2 py-0.5 rounded bg-amber-950/40 border border-amber-800/50 text-amber-300 font-mono inline-flex items-center gap-1"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                        {f}
                      </span>
                    );
                  }
                  return (
                    <span
                      key={i}
                      className="text-[11px] px-2 py-0.5 rounded bg-red-950/30 border border-red-900/30 text-red-400 font-mono"
                    >
                      {f}
                    </span>
                  );
                })}
              </div>
            )}

            {/* Execution Result Output (Sanitized) */}
            {act.execution_result && (
              <div className="space-y-1">
                <div className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
                  <FileText className="w-3 h-3" /> Execution Result (Sanitized DLP Output):
                </div>
                <pre className="p-2.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] text-[11px] font-mono text-emerald-400 max-h-32 overflow-x-auto whitespace-pre-wrap">
                  {act.execution_result}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
