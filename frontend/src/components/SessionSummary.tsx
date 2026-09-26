import React from 'react';
import { Download, ShieldCheck, AlertOctagon, Activity, Cpu } from 'lucide-react';
import { SessionRecord } from '../types';

interface SessionSummaryProps {
  session: SessionRecord | null;
  totalActions: number;
  blockedActions: number;
}

export const SessionSummary: React.FC<SessionSummaryProps> = ({
  session,
  totalActions,
  blockedActions,
}) => {
  const handleExport = () => {
    const url = session ? `/api/logs/export?session_id=${session.id}` : '/api/logs/export';
    window.open(url, '_blank');
  };

  const safePercentage =
    totalActions > 0 ? Math.round(((totalActions - blockedActions) / totalActions) * 100) : 100;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Total Actions Stat */}
      <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
        <div>
          <span className="text-xs text-slate-400 font-medium">Total Invocations</span>
          <h4 className="text-2xl font-bold font-mono text-slate-100 mt-1">{totalActions}</h4>
        </div>
        <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
          <Activity className="w-5 h-5" />
        </div>
      </div>

      {/* Blocked / Held Stat */}
      <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
        <div>
          <span className="text-xs text-slate-400 font-medium">Blocked / Flagged</span>
          <h4 className="text-2xl font-bold font-mono text-red-400 mt-1">{blockedActions}</h4>
        </div>
        <div className="p-3 rounded-xl bg-red-500/10 text-red-400">
          <AlertOctagon className="w-5 h-5" />
        </div>
      </div>

      {/* Security Health Rate */}
      <div className="p-5 rounded-2xl bg-[#121824] border border-[#1f293d] flex items-center justify-between">
        <div>
          <span className="text-xs text-slate-400 font-medium">Safe Clearance Rate</span>
          <h4 className="text-2xl font-bold font-mono text-emerald-400 mt-1">{safePercentage}%</h4>
        </div>
        <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
          <ShieldCheck className="w-5 h-5" />
        </div>
      </div>

      {/* Export Button Card */}
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
  );
};
