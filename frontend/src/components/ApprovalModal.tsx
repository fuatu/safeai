import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, XCircle, Clock, ShieldAlert, Code2, Eye } from 'lucide-react';
import { ExplainerMode, PendingApprovalEvent } from '../types';

interface ApprovalModalProps {
  approval: PendingApprovalEvent;
  explainerMode: ExplainerMode;
  onApprove: (actionId: string, notes?: string) => void;
  onDeny: (actionId: string, notes?: string) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  approval,
  explainerMode,
  onApprove,
  onDeny,
}) => {
  const isInfinite = !approval.timeoutSeconds || approval.timeoutSeconds <= 0;
  const [secondsRemaining, setSecondsRemaining] = useState<number>(isInfinite ? 0 : approval.timeoutSeconds || 90);
  const [notes, setNotes] = useState<string>('');
  const [localMode, setLocalMode] = useState<ExplainerMode>(explainerMode);

  // Sync mode if prop changes
  useEffect(() => {
    setLocalMode(explainerMode);
  }, [explainerMode]);

  // Countdown timer
  useEffect(() => {
    if (isInfinite) return;
    const elapsed = Math.floor(Date.now() / 1000 - approval.receivedAt);
    const initialRemaining = Math.max(0, (approval.timeoutSeconds || 90) - elapsed);
    setSecondsRemaining(initialRemaining);

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [approval, isInfinite]);

  const getRiskBadgeColor = (score: number) => {
    if (score >= 80) return 'bg-red-500/20 text-red-400 border-red-500/50';
    if (score >= 50) return 'bg-amber-500/20 text-amber-400 border-amber-500/50';
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
  };

  const getRiskLabel = (score: number) => {
    if (score >= 80) return 'CRITICAL THREAT';
    if (score >= 50) return 'ELEVATED RISK';
    return 'STANDARD RISK';
  };

  const formatPayload = (payload: Record<string, any>) => {
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return String(payload);
    }
  };

  const rawCommand =
    approval.rawPayload.command ||
    approval.rawPayload.cmd ||
    approval.rawPayload.CommandLine ||
    null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-100">
      <div className="relative w-full max-w-2xl bg-[#121824] border border-[#1f293d] rounded-2xl shadow-2xl overflow-hidden animate-urgent-glow">
        {/* Top Risk Header Banner */}
        <div className="px-6 py-4 border-b border-[#1f293d] flex items-center justify-between bg-gradient-to-r from-red-950/40 via-[#121824] to-transparent">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-red-500/20 text-red-400">
              <ShieldAlert className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg text-slate-100">Hold For Approval</h3>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium ${getRiskBadgeColor(
                    approval.riskScore
                  )}`}
                >
                  {getRiskLabel(approval.riskScore)} ({approval.riskScore}/100)
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Tool: <span className="text-blue-400 font-semibold">{approval.toolName}</span> | Session:{' '}
                {approval.sessionId.slice(0, 10)}...
              </p>
            </div>
          </div>

          {/* Countdown Clock */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] text-xs font-mono text-amber-400">
            <Clock className="w-4 h-4" />
            <span>{isInfinite ? '∞ Infinite' : `${secondsRemaining}s`}</span>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {/* Explainer Mode Toggle Buttons */}
          <div className="flex items-center justify-between border-b border-[#1f293d]/80 pb-3">
            <span className="text-xs text-slate-400 font-medium">Explainer View:</span>
            <div className="flex items-center gap-1 bg-[#0a0d14] p-1 rounded-lg border border-[#1f293d]">
              <button
                type="button"
                onClick={() => setLocalMode('plain')}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  localMode === 'plain'
                    ? 'bg-blue-600 text-white font-medium'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Plain Language
              </button>
              <button
                type="button"
                onClick={() => setLocalMode('technical')}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  localMode === 'technical'
                    ? 'bg-blue-600 text-white font-medium'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Technical
              </button>
              <button
                type="button"
                onClick={() => setLocalMode('off')}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  localMode === 'off'
                    ? 'bg-blue-600 text-white font-medium'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Off
              </button>
            </div>
          </div>

          {/* Mode: Plain Language (Req 3.4: summary prominently displayed above code) */}
          {localMode === 'plain' && (
            <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-900/40 text-blue-200">
              <div className="flex items-center gap-2 mb-1.5 text-xs text-blue-400 font-semibold uppercase tracking-wider">
                <Eye className="w-4 h-4" /> Real-World Consequence ({approval.activeLanguage.toUpperCase()})
              </div>
              <p className="text-sm leading-relaxed font-normal text-slate-100">
                {approval.plainExplanation}
              </p>
            </div>
          )}

          {/* Threat Factors List */}
          {approval.riskFactors && approval.riskFactors.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {approval.riskFactors.map((factor, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-md bg-red-950/40 border border-red-900/50 text-red-300 font-mono"
                >
                  <AlertTriangle className="w-3 h-3 text-red-400" />
                  {factor}
                </span>
              ))}
            </div>
          )}

          {/* Technical Details / Raw Command */}
          {localMode !== 'off' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                <span className="flex items-center gap-1.5">
                  <Code2 className="w-3.5 h-3.5 text-slate-400" /> Raw Action Payload
                </span>
              </div>
              <pre className="p-3.5 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-xs font-mono text-emerald-400 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {rawCommand ? `$ ${rawCommand}` : formatPayload(approval.rawPayload)}
              </pre>
            </div>
          )}

          {/* Mode: Technical (Req 3.5: summary displayed as secondary metadata) */}
          {localMode === 'technical' && (
            <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800 text-xs text-slate-400">
              <span className="font-semibold text-slate-300">Explainer note: </span>
              {approval.plainExplanation}
            </div>
          )}

          {/* Optional Decision Notes */}
          <div>
            <input
              type="text"
              placeholder="Optional notes for audit trail..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3.5 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="px-6 py-4 border-t border-[#1f293d] bg-[#0d121d] flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => onDeny(approval.actionId, notes)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-red-900/60 bg-red-950/30 hover:bg-red-900/50 text-red-300 text-sm font-medium transition-all shadow-sm active:scale-95"
          >
            <XCircle className="w-4 h-4 text-red-400" />
            Deny & Abort
          </button>
          <button
            type="button"
            onClick={() => onApprove(approval.actionId, notes)}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/30 active:scale-95"
          >
            <CheckCircle className="w-4 h-4 text-white" />
            Approve & Execute
          </button>
        </div>
      </div>
    </div>
  );
};
