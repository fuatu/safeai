import React, { useState, useMemo } from 'react';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Terminal,
  MessageSquare,
  Cpu,
  RefreshCw,
  Clock,
  ShieldAlert,
  ShieldCheck,
  Calendar,
  Layers,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { SessionRecord } from '../types';

interface SessionsPageProps {
  sessions: SessionRecord[];
  onSelectSession: (sessionId: string) => void;
}

export const SessionsPage: React.FC<SessionsPageProps> = ({
  sessions,
  onSelectSession,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedClient, setSelectedClient] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);

  // Filter out any sessions with 0 calls/turns
  const activeSessions = useMemo(() => {
    return sessions.filter((s) => (s.total_actions || 0) > 0);
  }, [sessions]);

  // Extract unique clients for filter tabs
  const clientOptions = useMemo(() => {
    const clients = new Set<string>();
    activeSessions.forEach((s) => {
      if (s.client_name) clients.add(s.client_name);
    });
    return Array.from(clients);
  }, [activeSessions]);

  // Sort: Most recent to oldest (by started_at descending)
  const sortedSessions = useMemo(() => {
    return [...activeSessions].sort((a, b) => {
      const timeA = new Date(a.started_at).getTime() || 0;
      const timeB = new Date(b.started_at).getTime() || 0;
      return timeB - timeA;
    });
  }, [activeSessions]);

  // Filter by search query and client
  const filteredSessions = useMemo(() => {
    return sortedSessions.filter((s) => {
      // Client filter
      if (selectedClient !== 'ALL' && s.client_name !== selectedClient) {
        return false;
      }

      // Search query
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      const matchTitle = (s.title || '').toLowerCase().includes(q);
      const matchClient = (s.client_name || '').toLowerCase().includes(q);
      const matchId = (s.id || '').toLowerCase().includes(q);
      const matchDate = new Date(s.started_at).toLocaleDateString().toLowerCase().includes(q);

      return matchTitle || matchClient || matchId || matchDate;
    });
  }, [sortedSessions, selectedClient, searchQuery]);

  // Pagination calculations
  const totalPages = Math.max(1, Math.ceil(filteredSessions.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedSessions = useMemo(() => {
    const start = (safeCurrentPage - 1) * pageSize;
    return filteredSessions.slice(start, start + pageSize);
  }, [filteredSessions, safeCurrentPage, pageSize]);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const formatCleanTitle = (session: SessionRecord) => {
    if (!session.title) {
      return `${session.client_name} Session`;
    }
    // Remove duplicate dates from title if present
    return session.title.replace(/\s*\([A-Za-z]{3}\s+\d+[^)]*\)\s*\([A-Za-z]{3}\s+\d+[^)]*\)/g, '');
  };

  const formatTimeAgo = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="p-6 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2.5">
              <Layers className="w-5 h-5 text-blue-400" /> AI Agent Sessions Directory
            </h2>
            <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-blue-950/60 text-blue-300 border border-blue-800/40">
              {filteredSessions.length} {filteredSessions.length === 1 ? 'session' : 'sessions'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Search, filter, and inspect past AI agent conversations, Copilot chat sessions, and guarded tool invocations. Ordered from most recent to oldest.
          </p>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="p-4 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Search Bar */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by prompt, title, client, or date..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-200 font-mono"
            >
              Clear
            </button>
          )}
        </div>

        {/* Client Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          <button
            type="button"
            onClick={() => {
              setSelectedClient('ALL');
              setCurrentPage(1);
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
              selectedClient === 'ALL'
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
            }`}
          >
            All Clients ({activeSessions.length})
          </button>
          {clientOptions.map((client) => {
            const count = activeSessions.filter((s) => s.client_name === client).length;
            const isCopilot = client.includes('Copilot');
            return (
              <button
                key={client}
                type="button"
                onClick={() => {
                  setSelectedClient(client);
                  setCurrentPage(1);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                  selectedClient === client
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#0a0d14]'
                }`}
              >
                {isCopilot ? <MessageSquare className="w-3 h-3 text-purple-400" /> : <Cpu className="w-3 h-3 text-cyan-400" />}
                {client} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Sessions Grid */}
      {paginatedSessions.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-[#121824] border border-[#1f293d] space-y-3">
          <Layers className="w-8 h-8 text-slate-500 mx-auto" />
          <h4 className="text-sm font-semibold text-slate-200">No matching sessions found</h4>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            {searchQuery
              ? `No sessions match "${searchQuery}". Try clearing your search term.`
              : 'Start a conversation in VS Code Copilot, Claude Desktop, or Cursor to record sessions.'}
          </p>
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="text-xs font-semibold text-cyan-400 hover:text-cyan-300"
            >
              Reset Search
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {paginatedSessions.map((s) => {
            const isCopilot = (s.client_name || '').includes('Copilot');
            const cleanTitle = formatCleanTitle(s);
            const formattedDate = new Date(s.started_at).toLocaleString([], {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });
            const timeAgo = formatTimeAgo(s.started_at);

            return (
              <div
                key={s.id}
                onClick={() => onSelectSession(s.id)}
                className="group p-5 rounded-2xl bg-[#121824] border border-[#1f293d] hover:border-blue-500/50 hover:bg-[#151d2c] transition-all cursor-pointer flex flex-col justify-between space-y-4 shadow-sm"
              >
                <div className="space-y-3">
                  {/* Top Meta Line: Client Badge & Relative Time */}
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium ${
                        isCopilot
                          ? 'bg-purple-950/50 text-purple-300 border border-purple-800/50'
                          : 'bg-cyan-950/50 text-cyan-300 border border-cyan-800/50'
                      }`}
                    >
                      {isCopilot ? (
                        <MessageSquare className="w-3 h-3 text-purple-400" />
                      ) : (
                        <Cpu className="w-3 h-3 text-cyan-400" />
                      )}
                      {s.client_name}
                    </span>

                    <span className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-500" />
                      {timeAgo}
                    </span>
                  </div>

                  {/* Title / Prompt Snippet */}
                  <div>
                    <h3 className="text-sm font-semibold text-slate-100 group-hover:text-blue-300 transition-colors line-clamp-2 leading-snug">
                      {cleanTitle}
                    </h3>
                    <p className="text-[11px] text-slate-500 font-mono mt-1 flex items-center gap-1.5">
                      <Calendar className="w-3 h-3" /> Started: {formattedDate}
                    </p>
                  </div>
                </div>

                {/* Footer Metrics & Action Button */}
                <div className="pt-3 border-t border-[#1f293d] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2.5 py-0.5 rounded-lg bg-[#0a0d14] border border-[#1f293d] text-slate-300 font-mono font-medium">
                      {s.total_actions} {s.total_actions === 1 ? 'turn' : 'turns'}
                    </span>

                    {s.blocked_actions > 0 ? (
                      <span className="text-xs px-2 py-0.5 rounded-lg bg-red-950/50 border border-red-800/50 text-red-300 font-mono font-medium flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3 text-red-400" /> {s.blocked_actions} blocked
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-emerald-400 font-mono flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-400" /> Safe
                      </span>
                    )}
                  </div>

                  <span className="text-xs font-semibold text-blue-400 group-hover:text-blue-300 flex items-center gap-1 transition-colors">
                    View Details <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {filteredSessions.length > pageSize && (
        <div className="p-4 rounded-2xl bg-[#121824] border border-[#1f293d] flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs text-slate-400 font-mono">
            Showing <strong className="text-slate-200">{(safeCurrentPage - 1) * pageSize + 1}</strong> to{' '}
            <strong className="text-slate-200">
              {Math.min(safeCurrentPage * pageSize, filteredSessions.length)}
            </strong>{' '}
            of <strong className="text-slate-200">{filteredSessions.length}</strong> sessions
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={safeCurrentPage <= 1}
              onClick={() => handlePageChange(safeCurrentPage - 1)}
              className="p-2 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-300 hover:text-white hover:bg-[#1a2333] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            {/* Page number buttons */}
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((pageNum) => {
                // Show first, last, and around current page
                if (
                  pageNum === 1 ||
                  pageNum === totalPages ||
                  (pageNum >= safeCurrentPage - 1 && pageNum <= safeCurrentPage + 1)
                ) {
                  return (
                    <button
                      key={pageNum}
                      type="button"
                      onClick={() => handlePageChange(pageNum)}
                      className={`min-w-[32px] h-8 px-2 rounded-xl text-xs font-mono font-medium transition-colors ${
                        pageNum === safeCurrentPage
                          ? 'bg-blue-600 text-white font-bold'
                          : 'bg-[#0a0d14] border border-[#1f293d] text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                } else if (pageNum === safeCurrentPage - 2 || pageNum === safeCurrentPage + 2) {
                  return (
                    <span key={pageNum} className="text-slate-600 font-mono px-1">
                      ...
                    </span>
                  );
                }
                return null;
              })}
            </div>

            <button
              type="button"
              disabled={safeCurrentPage >= totalPages}
              onClick={() => handlePageChange(safeCurrentPage + 1)}
              className="p-2 rounded-xl bg-[#0a0d14] border border-[#1f293d] text-slate-300 hover:text-white hover:bg-[#1a2333] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
