'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/server_api/client';
import type {
  QueueOverviewResponse,
  QueueTaskResponse,
  QueueTasksListResponse,
} from '@/server_api/client';
import ErrorLogViewer from '@/components/ErrorLogViewer';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type StatusFilter = 'all' | 'in_progress' | 'pending' | 'success' | 'failed';

function statusBadge(status: string) {
  switch (status) {
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300">
          <span className="h-1.5 w-1.5 rounded-full bg-yellow-500" />
          Pending
        </span>
      );
    case 'in_progress':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
          Processing
        </span>
      );
    case 'success':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300">
          <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
          Done
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300">
          <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
          Failed
        </span>
      );
    default:
      return <span className="text-xs text-gray-500">{status}</span>;
  }
}

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 5) return 'just now';
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function duration(startIso?: string, endIso?: string): string {
  if (!startIso) return '-';
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const sec = Math.max(0, Math.floor((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}

function trackLabel(t: QueueTaskResponse): string {
  if (t.track_artist && t.track_title) return `${t.track_artist} — ${t.track_title}`;
  if (t.track_title) return t.track_title;
  if (t.text_query) return `🔍 "${t.text_query}"`;
  if (t.track_id) return t.track_id;
  return '-';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50;

export default function ProcessingQueuePage() {
  // Overview (workers + stats + in-progress)
  const [overview, setOverview] = useState<QueueOverviewResponse | null>(null);

  // Task list with pagination
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [workerFilter, setWorkerFilter] = useState<string>('all');
  const [taskPage, setTaskPage] = useState<QueueTasksListResponse | null>(null);
  const [offset, setOffset] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ----- data fetching -----

  const fetchOverview = useCallback(async () => {
    try {
      const data = await api.getQueueOverview();
      setOverview(data);
    } catch {
      // silent — advisory
    }
  }, []);

  const fetchTasks = useCallback(async (status: StatusFilter, off: number, workerId: string) => {
    try {
      const data = await api.getQueueTasks({
        status: status === 'all' ? undefined : status,
        worker_id: workerId === 'all' ? undefined : workerId,
        limit: PAGE_SIZE,
        offset: off,
      });
      setTaskPage(data);
    } catch {
      // silent
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([fetchOverview(), fetchTasks(filter, offset, workerFilter)]);
    setLoading(false);
  }, [fetchOverview, fetchTasks, filter, offset, workerFilter]);

  // Initial load + auto-refresh every 3s
  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  // When filter changes, reset offset
  const changeFilter = (f: StatusFilter) => {
    setFilter(f);
    setOffset(0);
  };

  const changeWorkerFilter = (w: string) => {
    setWorkerFilter(w);
    setOffset(0);
  };

  // ----- cancel -----

  const handleCancel = async (taskId: string) => {
    setError(null);
    try {
      const res = await api.cancelTask({ taskId });
      if (!res.success) setError(res.message);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel task');
    }
  };

  // ----- render -----

  if (loading && !overview) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">📋 Processing Queue</h2>
        <div className="animate-pulse space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-gray-200 dark:bg-gray-700 h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const stats = overview?.stats;
  const workers = overview?.workers ?? [];

  return (
    <div className="space-y-6">
      {/* ---- Error banner ---- */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {/* ---- Workers Panel ---- */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">🖥️ Workers</h3>
        {workers.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400 text-sm">No workers registered yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {workers.map((w) => (
              <div
                key={w.id}
                className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 bg-gray-50 dark:bg-gray-700/50"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      w.is_active
                        ? 'bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]'
                        : 'bg-gray-400'
                    }`}
                    aria-label={w.is_active ? 'Active' : 'Inactive'}
                  />
                  <span className="font-medium text-gray-900 dark:text-white text-sm truncate" title={w.id}>
                    {w.id}
                  </span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  <p>IP: {w.ip_address}</p>
                  {w.gpu_name && (
                    <p title={w.gpu_name}>
                      <span className="text-purple-600 dark:text-purple-400">⚡</span> {w.gpu_name}
                    </p>
                  )}
                  <p>Last seen: {relativeTime(w.last_heartbeat)}</p>
                </div>
                {w.current_task ? (
                  <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                    <p className="text-xs font-medium text-blue-600 dark:text-blue-400 truncate" title={trackLabel(w.current_task)}>
                      ▶ {trackLabel(w.current_task)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {duration(w.current_task.started_at)}
                    </p>
                  </div>
                ) : (
                  <p className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 text-xs text-gray-400 italic">
                    Idle
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Stats Bar ---- */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {([
            { label: 'Workers', value: stats.active_workers, color: 'text-purple-600 dark:text-purple-400' },
            { label: 'Pending', value: stats.pending_tasks, color: 'text-yellow-600 dark:text-yellow-400' },
            { label: 'Processing', value: stats.in_progress_tasks, color: 'text-blue-600 dark:text-blue-400' },
            { label: 'Completed', value: stats.completed_tasks, color: 'text-green-600 dark:text-green-400' },
            { label: 'Failed', value: stats.failed_tasks, color: 'text-red-600 dark:text-red-400' },
            { label: 'Total', value: stats.total_tasks, color: 'text-gray-600 dark:text-gray-400' },
          ] as const).map((s) => (
            <div
              key={s.label}
              className="bg-white dark:bg-gray-800 rounded-lg shadow px-4 py-3 text-center"
            >
              <p className={`text-2xl font-bold ${s.color}`}>{s.value.toLocaleString()}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* ---- Task List ---- */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
        {/* Status filter tabs + worker filter */}
        <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-600 px-4 pt-4">
          <div className="flex gap-1 overflow-x-auto">
            {([
              { id: 'all' as StatusFilter, label: 'All' },
              { id: 'in_progress' as StatusFilter, label: 'Processing' },
              { id: 'pending' as StatusFilter, label: 'Pending' },
              { id: 'success' as StatusFilter, label: 'Completed' },
              { id: 'failed' as StatusFilter, label: 'Failed' },
            ]).map((tab) => (
              <button
                key={tab.id}
                onClick={() => changeFilter(tab.id)}
                className={`px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap ${
                  filter === tab.id
                    ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 border-b-2 border-purple-600 dark:border-purple-400'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {tab.label}
                {stats && (
                  <span className="ml-1.5 text-xs opacity-60">
                    {tab.id === 'all' ? stats.total_tasks
                      : tab.id === 'in_progress' ? stats.in_progress_tasks
                      : tab.id === 'pending' ? stats.pending_tasks
                      : tab.id === 'success' ? stats.completed_tasks
                      : stats.failed_tasks}
                  </span>
                )}
              </button>
            ))}
          </div>

          {workers.length > 0 && (
            <select
              value={workerFilter}
              onChange={(e) => changeWorkerFilter(e.target.value)}
              className="ml-4 mb-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1.5 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              aria-label="Filter by worker"
            >
              <option value="all">All Workers</option>
              {workers.map((w) => (
                <option key={w.id} value={w.id}>{w.id}</option>
              ))}
            </select>
          )}
        </div>

        {/* Task table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 text-left">
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Track</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Album</th>
                <th className="px-4 py-3 font-medium hidden lg:table-cell">Worker</th>
                <th className="px-4 py-3 font-medium hidden sm:table-cell">Created</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Duration</th>
                <th className="px-4 py-3 font-medium w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {taskPage?.tasks.map((task) => (
                <tr key={task.task_id} className="hover:bg-gray-50 dark:hover:bg-gray-700/40 transition-colors">
                  <td className="px-4 py-2.5">{statusBadge(task.status)}</td>
                  <td className="px-4 py-2.5 max-w-xs truncate text-gray-900 dark:text-white" title={trackLabel(task)}>
                    {trackLabel(task)}
                  </td>
                  <td className="px-4 py-2.5 hidden md:table-cell text-gray-500 dark:text-gray-400 max-w-[150px] truncate" title={task.track_album ?? ''}>
                    {task.track_album || '-'}
                  </td>
                  <td className="px-4 py-2.5 hidden lg:table-cell text-gray-500 dark:text-gray-400 max-w-[120px] truncate" title={task.assigned_worker_id ?? ''}>
                    {task.assigned_worker_id || '-'}
                  </td>
                  <td className="px-4 py-2.5 hidden sm:table-cell text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {task.created_at ? relativeTime(task.created_at) : '-'}
                  </td>
                  <td className="px-4 py-2.5 hidden md:table-cell text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {duration(task.started_at, task.completed_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    {task.status === 'pending' && (
                      <button
                        onClick={() => handleCancel(task.task_id)}
                        className="text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 font-medium"
                        title="Cancel this task"
                      >
                        Cancel
                      </button>
                    )}
                    {task.status === 'failed' && task.error_message && (
                      <span
                        className="text-xs text-red-500 cursor-help"
                        title={task.error_message}
                      >
                        ⚠️
                      </span>
                    )}
                  </td>
                </tr>
              ))}

              {taskPage && taskPage.tasks.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400 dark:text-gray-500">
                    <p className="text-lg mb-2">No tasks found</p>
                    <p className="text-sm">Start processing from the Library page to see tasks here.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {taskPage && taskPage.total_count > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-600">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, taskPage.total_count)} of{' '}
              {taskPage.total_count.toLocaleString()}
            </p>
            <div className="flex gap-2">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                className="px-3 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                Previous
              </button>
              <button
                disabled={offset + PAGE_SIZE >= taskPage.total_count}
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className="px-3 py-1 text-sm rounded border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ---- Error Log ---- */}
      <ErrorLogViewer />
    </div>
  );
}
