import React from 'react';
import { ActionLog } from '../types';
import { ShieldCheck, ShieldAlert, Clock, CheckCircle2, XCircle, Terminal, FileText } from 'lucide-react';

interface SessionTimelineProps {
  actions: ActionLog[];
  isLoading?: boolean;
}

export const SessionTimeline: React.FC<SessionTimelineProps> = ({ actions, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-500 font-mono text-sm">
        Loading session activity...
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-500 bg-[#121824] rounded-2xl border border-[#1f293d]">
        <Terminal className="w-10 h-10 mb-3 text-slate-600" />
        <p className="text-sm font-medium">No intercepted actions recorded yet.</p>
        <p className="text-xs text-slate-600 mt-1">Actions performed by AI agents will stream here in real time.</p>
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
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-100">{act.tool_name}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-md border font-mono font-medium ${getRiskScoreColor(
                        act.risk_score
                      )}`}
                    >
                      Risk {act.risk_score}/100
                    </span>
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

            {/* Risk factors tags */}
            {factors.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {factors.map((f, i) => (
                  <span
                    key={i}
                    className="text-[11px] px-2 py-0.5 rounded bg-red-950/30 border border-red-900/30 text-red-400 font-mono"
                  >
                    {f}
                  </span>
                ))}
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
