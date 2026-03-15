'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { workerApi } from '@/worker_api/client';
import type { WorkerConfigResponse, ClientStatusResponse } from '@/worker_api/client';

export default function ClientSettingsPage() {
  const [config, setConfig] = useState<WorkerConfigResponse | null>(null);
  const [originalConfig, setOriginalConfig] = useState<WorkerConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [status, setStatus] = useState<ClientStatusResponse | null>(null);
  const statusInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await workerApi.getClientStatus();
      setStatus(s);
    } catch {
      // Silently ignore — status is advisory
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchStatus();
    statusInterval.current = setInterval(fetchStatus, 5000);
    return () => {
      if (statusInterval.current) clearInterval(statusInterval.current);
    };
  }, [fetchStatus]);

  const fetchConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg = await workerApi.getWorkerConfig();
      setConfig(cfg);
      setOriginalConfig(JSON.parse(JSON.stringify(cfg)) as WorkerConfigResponse);
    } catch {
      setError(
        'Unable to fetch client configuration. Ensure the worker API is running and reachable.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;

    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await workerApi.saveWorkerConfig({ workerConfigRequest: config });
      setOriginalConfig(JSON.parse(JSON.stringify(config)) as WorkerConfigResponse);
      setSuccessMessage(result.message ?? 'Configuration saved successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (originalConfig) {
      setConfig(JSON.parse(JSON.stringify(originalConfig)));
      setError(null);
      setSuccessMessage(null);
    }
  };

  const hasChanges = () => {
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  };

  const updateConfig = <K extends keyof WorkerConfigResponse, P extends keyof WorkerConfigResponse[K]>(
    section: K,
    key: P,
    value: WorkerConfigResponse[K][P]
  ) => {
    setConfig(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [section]: {
          ...(prev[section] as WorkerConfigResponse[K]),
          [key]: value as WorkerConfigResponse[K][P],
        },
      } as WorkerConfigResponse;
    });
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          ⚙️ Client Settings
        </h2>
        <div className="animate-pulse space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-gray-200 dark:bg-gray-700 h-20 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="p-6 border-b border-gray-200 dark:border-gray-600">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          ⚙️ Client Settings
        </h2>
        <p className="text-gray-600 dark:text-gray-300">
          Configure your Mycelium client worker. Changes are applied immediately with hot-reload.
        </p>
      </div>

      {/* Live Status Panel */}
      {status && (
        <div className="px-6 pt-4">
          <div className="rounded-lg border border-gray-200 dark:border-gray-600 p-4 bg-gray-50 dark:bg-gray-700/50">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              {/* Server reachability */}
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    status.server_reachable
                      ? 'bg-green-500 shadow-[0_0_4px_rgba(34,197,94,0.6)]'
                      : 'bg-red-500 shadow-[0_0_4px_rgba(239,68,68,0.6)]'
                  }`}
                  aria-label={status.server_reachable ? 'Server reachable' : 'Server unreachable'}
                />
                <span className="text-gray-700 dark:text-gray-300">
                  Server{' '}
                  <span className={status.server_reachable ? 'text-green-600 dark:text-green-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                    {status.server_reachable ? 'Reachable' : 'Unreachable'}
                  </span>
                </span>
              </div>

              <span className="hidden sm:inline text-gray-300 dark:text-gray-500">|</span>

              {/* Worker state */}
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2.5 w-2.5 rounded-full ${
                    !status.worker.is_running
                      ? 'bg-gray-400'
                      : status.worker.is_processing
                        ? 'bg-green-500 animate-pulse shadow-[0_0_4px_rgba(34,197,94,0.6)]'
                        : 'bg-yellow-400 shadow-[0_0_4px_rgba(250,204,21,0.6)]'
                  }`}
                  aria-label={
                    !status.worker.is_running ? 'Worker stopped' : status.worker.is_processing ? 'Processing' : 'Idle'
                  }
                />
                <span className="text-gray-700 dark:text-gray-300">
                  Worker{' '}
                  <span
                    className={
                      !status.worker.is_running
                        ? 'text-gray-500 font-medium'
                        : status.worker.is_processing
                          ? 'text-green-600 dark:text-green-400 font-medium'
                          : 'text-yellow-600 dark:text-yellow-400 font-medium'
                    }
                  >
                    {!status.worker.is_running ? 'Stopped' : status.worker.is_processing ? 'Processing' : 'Idle'}
                  </span>
                </span>
              </div>

              <span className="hidden sm:inline text-gray-300 dark:text-gray-500">|</span>

              {/* Queue stats */}
              <div className="flex items-center gap-3 text-gray-600 dark:text-gray-400">
                <span title="Jobs waiting to be downloaded">
                  📥 {status.worker.jobs_in_download_queue} queued
                </span>
                <span title="Jobs downloaded and ready for GPU">
                  🧠 {status.worker.jobs_ready_for_gpu} ready
                </span>
                <span title="Total jobs processed this session">
                  ✅ {status.worker.total_jobs_processed} done
                </span>
              </div>

              {/* Model info (assigned by server) */}
              {status.worker.model_type && (
                <>
                  <span className="hidden sm:inline text-gray-300 dark:text-gray-500">|</span>
                  <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                    <span title="Embedding model assigned by server">
                      🎵 {status.worker.model_type.toUpperCase()}: {status.worker.model_id}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="p-6 space-y-8">
        {error && (
          <div className="bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {successMessage && (
          <div className="bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-700 rounded-lg p-4">
            <p className="text-green-700 dark:text-green-300">{successMessage}</p>
          </div>
        )}

        {config && (
          <>
            {/* Client Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🖥️ Client Worker
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-7 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server Host
                  </label>
                  <input
                    type="text"
                    value={config.client.server_host}
                    onChange={(e) => updateConfig('client', 'server_host', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server Port
                  </label>
                  <input
                    type="number"
                    value={config.client.server_port}
                    onChange={(e) => updateConfig('client', 'server_port', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="8000"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Download Queue Size
                  </label>
                  <input
                    type="number"
                    value={config.client.download_queue_size}
                    onChange={(e) => updateConfig('client', 'download_queue_size', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="15"
                    min="1"
                    max="100"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Max audio files to download simultaneously
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Job Queue Size
                  </label>
                  <input
                    type="number"
                    value={config.client.job_queue_size}
                    onChange={(e) => updateConfig('client', 'job_queue_size', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="30"
                    min="1"
                    max="500"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Max jobs to queue for processing
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Poll Interval (s)
                  </label>
                  <input
                    type="number"
                    value={config.client.poll_interval}
                    onChange={(e) => updateConfig('client', 'poll_interval', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="5"
                    min="1"
                    max="60"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Seconds between job requests
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Download Workers
                  </label>
                  <input
                    type="number"
                    value={config.client.download_workers}
                    onChange={(e) => updateConfig('client', 'download_workers', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="10"
                    min="1"
                    max="50"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Parallel download threads
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    GPU Batch Size
                  </label>
                  <input
                    type="number"
                    value={config.client.gpu_batch_size}
                    onChange={(e) => updateConfig('client', 'gpu_batch_size', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="4"
                    min="1"
                    max="32"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    GPU processing batch size
                  </p>
                </div>
              </div>
            </div>

            {/* Client API Server Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🔌 Client API Server
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Configure the local API server for client configuration management.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API Host
                  </label>
                  <input
                    type="text"
                    value={config.client_api.host}
                    onChange={(e) => updateConfig('client_api', 'host', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API Port
                  </label>
                  <input
                    type="number"
                    value={config.client_api.port}
                    onChange={(e) => updateConfig('client_api', 'port', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="3001"
                  />
                </div>
              </div>
            </div>

            {/* Logging Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                📝 Logging
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Log Level
                  </label>
                  <select
                    value={config.logging.level}
                    onChange={(e) => updateConfig('logging', 'level', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between items-center pt-6 border-t border-gray-200 dark:border-gray-600">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Configuration is stored in ~/.config/mycelium/client_config.yml
              </div>
              <div className="space-x-3">
                <button
                  onClick={handleReset}
                  disabled={!hasChanges() || saving}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Reset
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasChanges() || saving}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}