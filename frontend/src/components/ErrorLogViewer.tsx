'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/server_api/client';
import type { ErrorLogEntry, ErrorLogResponse } from '@/server_api/client';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  download_404: { label: '404 Not Found', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300' },
  download_500: { label: '500 Server Error', color: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
  download_timeout: { label: 'Timeout', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' },
  download_connection: { label: 'Connection Error', color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' },
  download_error: { label: 'Download Error', color: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300' },
  processing: { label: 'Processing Error', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300' },
};

function categoryBadge(category: string) {
  const cat = CATEGORY_LABELS[category] ?? { label: category, color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300' };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cat.color}`}>
      {cat.label}
    </span>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function trackLabel(e: ErrorLogEntry): string {
  if (e.track_artist && e.track_title) return `${e.track_artist} — ${e.track_title}`;
  if (e.track_title) return e.track_title;
  if (e.track_id) return e.track_id;
  return '-';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50;

export default function ErrorLogViewer() {
  const [data, setData] = useState<ErrorLogResponse | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (cat: string, off: number) => {
    try {
      const res = await api.getErrorLog({
        category: cat === 'all' ? undefined : cat,
        limit: PAGE_SIZE,
        offset: off,
      });
      setData(res);
    } catch {
      // silent
    }
    setLoading(false);
  }, []);

  const refresh = useCallback(() => {
    fetchData(categoryFilter, offset);
  }, [fetchData, categoryFilter, offset]);

  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, 5000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  const changeCategory = (cat: string) => {
    setCategoryFilter(cat);
    setOffset(0);
  };

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleClear = async () => {
    await api.clearErrorLog();
    refresh();
  };

  const totalErrors = data ? Object.values(data.categories).reduce((a, b) => a + b, 0) : 0;

  if (loading && !data) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">🔴 Error Log</h3>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-gray-200 dark:bg-gray-700 h-12 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (totalErrors === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mt-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">🔴 Error Log</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">No errors recorded.</p>
      </div>
    );
  }

  const categories = data?.categories ?? {};
  const entries = data?.entries ?? [];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg mt-6">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          🔴 Error Log
          <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
            ({totalErrors} total)
          </span>
        </h3>
        <button
          onClick={handleClear}
          className="text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 font-medium px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          Clear All
        </button>
      </div>

      {/* Category filter pills */}
      <div className="flex flex-wrap gap-2 px-6 pb-3">
        <button
          onClick={() => changeCategory('all')}
          className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
            categoryFilter === 'all'
              ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
        >
          All ({totalErrors})
        </button>
        {Object.entries(categories).sort((a, b) => b[1] - a[1]).map(([cat, count]) => {
          const meta = CATEGORY_LABELS[cat];
          return (
            <button
              key={cat}
              onClick={() => changeCategory(cat)}
              className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                categoryFilter === cat
                  ? 'bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {meta?.label ?? cat} ({count})
            </button>
          );
        })}
      </div>

      {/* Entries */}
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/40 cursor-pointer transition-colors"
            onClick={() => toggleExpand(entry.id)}
          >
            <div className="flex items-start gap-3">
              {/* Timestamp */}
              <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap pt-0.5 min-w-[110px]">
                {formatTimestamp(entry.timestamp)}
              </span>

              {/* Category badge */}
              <div className="min-w-[120px]">
                {categoryBadge(entry.category)}
              </div>

              {/* Track info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 dark:text-white truncate" title={trackLabel(entry)}>
                  {trackLabel(entry)}
                </p>
                {entry.track_album && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {entry.track_album}
                  </p>
                )}
              </div>

              {/* Worker */}
              {entry.worker_id && (
                <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap hidden md:block" title={entry.worker_id}>
                  {entry.worker_id}
                </span>
              )}

              {/* Expand indicator */}
              <span className="text-gray-400 text-xs pt-0.5">
                {expanded.has(entry.id) ? '▼' : '▶'}
              </span>
            </div>

            {/* Expanded details */}
            {expanded.has(entry.id) && (
              <div className="mt-2 ml-[110px] pl-3 border-l-2 border-gray-200 dark:border-gray-600 space-y-1">
                <p className="text-xs text-gray-700 dark:text-gray-300 font-mono break-all">
                  {entry.message}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                  {entry.track_id && <span>Track ID: <span className="font-mono">{entry.track_id}</span></span>}
                  {entry.task_id && <span>Task: <span className="font-mono">{entry.task_id.slice(0, 8)}</span></span>}
                  {entry.worker_id && <span>Worker: {entry.worker_id}</span>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {data && data.total_count > PAGE_SIZE && (
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 dark:border-gray-600">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total_count)} of {data.total_count}
          </p>
          <div className="flex gap-2">
            <button
              disabled={offset === 0}
              onClick={(e) => { e.stopPropagation(); setOffset(Math.max(0, offset - PAGE_SIZE)); }}
              className="px-3 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              Previous
            </button>
            <button
              disabled={offset + PAGE_SIZE >= data.total_count}
              onClick={(e) => { e.stopPropagation(); setOffset(offset + PAGE_SIZE); }}
              className="px-3 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
