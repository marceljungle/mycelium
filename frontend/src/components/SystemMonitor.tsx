'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { workerApi } from '@/worker_api/client';
import type { ClientStatusResponse } from '@/worker_api/client';

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds.toFixed(1)}s`;
}

function formatUptime(startedAt: number | null): string {
  if (!startedAt) return '—';
  const elapsed = Math.floor(Date.now() / 1000 - startedAt);
  if (elapsed < 60) return `${elapsed}s`;
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  return `${h}h ${m}m`;
}

interface PipelineStageProps {
  label: string;
  icon: string;
  active: boolean;
  count: number | string;
  sublabel?: string;
  activeClasses: string;
}

function PipelineStage({ label, icon, active, count, sublabel, activeClasses }: PipelineStageProps) {
  return (
    <div className={`
      relative flex flex-col items-center p-4 rounded-xl border-2 transition-all duration-300 min-w-[100px]
      ${active
        ? activeClasses
        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
      }
    `}>
      {active && (
        <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-green-400 animate-pulse" />
      )}
      <span className="text-2xl mb-1">{icon}</span>
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </span>
      <span className={`text-xl font-bold mt-1 ${active ? 'text-gray-900 dark:text-white' : 'text-gray-500 dark:text-gray-400'}`}>
        {count}
      </span>
      {sublabel && (
        <span className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sublabel}</span>
      )}
    </div>
  );
}

function PipelineArrow() {
  return (
    <div className="flex items-center justify-center px-1">
      <svg className="w-6 h-6 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </div>
  );
}

export default function SystemMonitor() {
  const [status, setStatus] = useState<ClientStatusResponse | null>(null);
  const [error, setError] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await workerApi.getClientStatus();
      setStatus(s);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 1500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchStatus]);

  if (error || !status) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          📊 System Monitor
        </h2>
        <p className="text-gray-500 dark:text-gray-400 text-sm">
          {error ? 'Unable to reach worker API' : 'Loading...'}
        </p>
      </div>
    );
  }

  const w = status.worker;

  if (!w.is_running) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          📊 System Monitor
        </h2>
        <p className="text-gray-500 dark:text-gray-400 text-sm">Worker is not running.</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
          📊 System Monitor
        </h2>
        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          <span>⏱ {formatUptime(w.pipeline_started_at)}</span>
          <span>✅ {w.total_jobs_processed} processed</span>
          <span className="font-medium text-purple-600 dark:text-purple-400">
            ⚡ {w.jobs_per_minute} jobs/min
          </span>
        </div>
      </div>

      {/* Pipeline visualization */}
      <div className="flex items-center justify-between gap-1">
        <PipelineStage
          label="Download"
          icon="⬇️"
          active={w.active_downloads > 0}
          count={w.active_downloads}
          sublabel={`${w.jobs_in_download_queue} queued`}
          activeClasses="border-blue-400 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-500 shadow-lg"
        />
        <PipelineArrow />
        <PipelineStage
          label="Preprocess"
          icon="🔄"
          active={w.is_preprocessing}
          count={w.is_preprocessing ? w.preprocessing_files : 0}
          sublabel={w.last_preprocess_duration !== null ? `last: ${formatDuration(w.last_preprocess_duration)}` : undefined}
          activeClasses="border-amber-400 bg-amber-50 dark:bg-amber-900/30 dark:border-amber-500 shadow-lg"
        />
        <PipelineArrow />
        <PipelineStage
          label="GPU Ready"
          icon="📦"
          active={w.jobs_ready_for_gpu > 0}
          count={w.jobs_ready_for_gpu}
          sublabel="batches"
          activeClasses="border-purple-400 bg-purple-50 dark:bg-purple-900/30 dark:border-purple-500 shadow-lg"
        />
        <PipelineArrow />
        <PipelineStage
          label="GPU"
          icon="🚀"
          active={w.is_gpu_busy}
          count={w.is_gpu_busy ? w.gpu_batch_chunks : 0}
          sublabel={w.last_gpu_duration !== null ? `last: ${formatDuration(w.last_gpu_duration)}` : undefined}
          activeClasses="border-green-400 bg-green-50 dark:bg-green-900/30 dark:border-green-500 shadow-lg"
        />
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-100 dark:border-gray-700">
        <div className="text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Model</p>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mt-1 truncate">
            {w.model_type?.toUpperCase() ?? '—'}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Batch Size</p>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mt-1">
            {w.micro_batch_size ?? '—'} chunks
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Last Preprocess</p>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mt-1">
            {formatDuration(w.last_preprocess_duration)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Last GPU</p>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mt-1">
            {formatDuration(w.last_gpu_duration)}
          </p>
        </div>
      </div>
    </div>
  );
}
