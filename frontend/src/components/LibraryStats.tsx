'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';

interface LibraryStats {
  total_embeddings: number;
  collection_name: string;
  database_path: string;
  track_database_stats?: {
    total_tracks: number;
    processed_tracks: number;
    unprocessed_tracks: number;
    progress_percentage: number;
    is_processing?: boolean;
    latest_session?: Record<string, unknown>;
  };
}

interface ProgressInfo {
  stage: string;
  current?: number;
  total?: number;
  processed?: number;
  failed?: number;
  current_track?: string;
  result?: Record<string, unknown>;
}

export default function LibraryStats() {
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [processLoading, setProcessLoading] = useState(false);
  const [operationMessage, setOperationMessage] = useState<string | null>(null);
  const [progressInfo, setProgressInfo] = useState<ProgressInfo | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/stats`);
      if (!response.ok) {
        throw new Error('Failed to fetch library stats');
      }
      const data = await response.json();
      setStats(data);
      setError(null);
    } catch (_err) {
      setError('Unable to connect to API');
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchProgress = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/progress`);
      if (response.ok) {
        const data = await response.json();
        if (stats) {
          setStats(prev => prev ? { ...prev, track_database_stats: data } : null);
        }

        // Only update processing state if we haven't explicitly stopped
        if (data.is_processing && !processLoading && !operationMessage?.includes('Stop signal sent')) {
          setProcessLoading(true);
          setProgressInfo({ stage: 'processing' });
        } else if (!data.is_processing && processLoading && !operationMessage?.includes('Stop signal sent')) {
          setProcessLoading(false);
          setProgressInfo(null);
          if (operationMessage?.includes('started')) {
            setOperationMessage('✅ Processing completed! Check the progress above for details.');
          }
        }
      }
    } catch (_err) {
      // Ignore progress fetch errors
    }
  }, [stats, processLoading, operationMessage]);

  const scanLibrary = async () => {
    setScanLoading(true);
    setOperationMessage(null);
    setProgressInfo(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/scan`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to scan library');
      }
      const data = await response.json();
      setOperationMessage(
        `✅ Scan completed! Found ${data.total_tracks} total tracks ` +
        `(${data.new_tracks} new, ${data.updated_tracks} updated)`
      );
      // Refresh stats after scanning
      await fetchStats();
      await fetchProgress();
    } catch (_err) {
      setOperationMessage('❌ Failed to scan library. Make sure the API server is running and Plex is accessible.');
    } finally {
      setScanLoading(false);
    }
  };

  const processEmbeddings = async () => {
    setProcessLoading(true);
    setOperationMessage(null);
    setProgressInfo({ stage: 'starting' });

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start processing');
      }
      const data = await response.json();

      if (data.status === 'already_running') {
        setOperationMessage('⚠️ Processing is already in progress');
        setProcessLoading(false);
        setProgressInfo(null);
        return;
      }

      if (data.status === 'worker_processing_started') {
        setOperationMessage(`🚀 Worker processing started! Created ${data.tasks_created} tasks for ${data.active_workers} workers. Progress will be updated automatically.`);
        // Don't set processLoading to false - let the progress monitoring handle it
        return;
      }

      if (data.status === 'no_workers' && data.confirmation_required) {
        setOperationMessage('⚠️ No client workers detected. Server processing will use local hardware.');
        setShowConfirmation(true);
        setProcessLoading(false);
        setProgressInfo(null);
        return;
      }

      // Handle other status types
      if (data.status === 'server_started') {
        setOperationMessage('🚀 Server processing started! Progress will be updated automatically.');
        return;
      }

      // Default success case (backward compatibility)
      setOperationMessage('🚀 Processing started! Progress will be updated automatically.');

    } catch (_err) {
      setOperationMessage('❌ Failed to start processing. Make sure the API server is running.');
      setProcessLoading(false);
      setProgressInfo(null);
    }
  };

  const processOnServer = async () => {
    setProcessLoading(true);
    setShowConfirmation(false);
    setOperationMessage(null);
    setProgressInfo({ stage: 'starting' });

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process/server`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start server processing');
      }
      const data = await response.json();

      if (data.status === 'already_running') {
        setOperationMessage('⚠️ Processing is already in progress');
        setProcessLoading(false);
        setProgressInfo(null);
        return;
      }

      setOperationMessage('🖥️ Server processing started! This may take longer on low-power hardware. Progress will be updated automatically.');

    } catch (_err) {
      setOperationMessage('❌ Failed to start server processing. Make sure the API server is running.');
      setProcessLoading(false);
      setProgressInfo(null);
    }
  };

  const cancelConfirmation = () => {
    setShowConfirmation(false);
    setOperationMessage(null);
  };

  const stopProcessing = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process/stop`, {
        method: 'POST',
      });
      if (response.ok) {
        // Clear progress info and processing state immediately when stop is requested
        setProgressInfo(null);
        setProcessLoading(false);
        setOperationMessage('🛑 Stop signal sent. Processing will finish current track and stop.');
      }
    } catch (_err) {
      setOperationMessage('❌ Failed to send stop signal.');
    }
  };

  useEffect(() => {
    fetchStats();
    fetchProgress();

    // Refresh stats and progress every 5 seconds
    const interval = setInterval(() => {
      fetchStats();
      fetchProgress();
    }, 5000);

    return () => clearInterval(interval);
  }, []); // Remove fetchStats and fetchProgress from dependencies to prevent multiple intervals

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          📊 Library Statistics
        </h3>
        <div className="animate-pulse space-y-3">
          <div className="bg-gray-200 dark:bg-gray-700 h-4 rounded"></div>
          <div className="bg-gray-200 dark:bg-gray-700 h-4 rounded w-3/4"></div>
          <div className="bg-gray-200 dark:bg-gray-700 h-4 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  const renderProgressBar = (percentage: number, label: string) => (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600 dark:text-gray-400">{label}</span>
        <span className="text-gray-900 dark:text-white font-medium">{percentage.toFixed(1)}%</span>
      </div>
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className="bg-gradient-to-r from-purple-600 to-blue-600 h-2 rounded-full transition-all duration-300"
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
    </div>
  );

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📊 Library Management
      </h3>

      {error ? (
        <div className="text-center py-6">
          <div className="text-4xl mb-2">⚠️</div>
          <p className="text-red-600 dark:text-red-400 font-medium">
            {error}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Start the API server to view stats
          </p>
          <button
            onClick={fetchStats}
            className="mt-3 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm"
          >
            Retry
          </button>
        </div>
      ) : stats ? (
        <div className="space-y-4">
          {/* Track Database Stats */}
          <div className="bg-gradient-to-r from-blue-100 to-cyan-100 dark:from-blue-900 dark:to-cyan-900 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4 mb-3">
              <div>
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {stats.track_database_stats?.total_tracks?.toLocaleString() || '0'}
                </div>
                <div className="text-sm text-blue-700 dark:text-blue-300">
                  Total Scanned Tracks
                </div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {stats.track_database_stats?.processed_tracks?.toLocaleString() || '0'}
                </div>
                <div className="text-sm text-green-700 dark:text-green-300">
                  Processed Tracks
                </div>
              </div>
            </div>

            {stats.track_database_stats && stats.track_database_stats.total_tracks > 0 && (
              <div className="mt-3">
                {renderProgressBar(
                  stats.track_database_stats.progress_percentage || 0,
                  "Processing Progress"
                )}
              </div>
            )}
            
            {(!stats.track_database_stats || stats.track_database_stats.total_tracks === 0) && (
              <div className="text-center py-2">
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  📖 No tracks scanned yet. Use &quot;Scan Library&quot; below to get started.
                </p>
              </div>
            )}
          </div>

          {/* Vector Database Stats */}
          <div className="bg-gradient-to-r from-purple-100 to-pink-100 dark:from-purple-900 dark:to-pink-900 p-4 rounded-lg">
            <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
              {stats.total_embeddings.toLocaleString()}
            </div>
            <div className="text-sm text-purple-700 dark:text-purple-300">
              Embeddings in Vector DB
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Collection</div>
              <div className="font-medium text-gray-900 dark:text-white">
                {stats.collection_name}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Database Path</div>
              <div className="font-mono text-xs text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 p-2 rounded">
                {stats.database_path}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-6">
          <div className="text-4xl mb-2">🎵</div>
          <p className="text-gray-500 dark:text-gray-400">
            No data available
          </p>
        </div>
      )}

      {/* Operations */}
      <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-600">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
          Library Operations
        </h4>

        {operationMessage && (
          <div className="mb-3 p-3 bg-blue-50 dark:bg-blue-900/50 border border-blue-200 dark:border-blue-700 rounded-lg">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              {operationMessage}
            </p>
          </div>
        )}

        {progressInfo && (
          <div className="mb-3 p-3 bg-yellow-50 dark:bg-yellow-900/50 border border-yellow-200 dark:border-yellow-700 rounded-lg">
            <p className="text-sm text-yellow-700 dark:text-yellow-300">
              {progressInfo.stage === 'starting' && '🚀 Starting processing...'}
              {progressInfo.stage === 'processing' && (
                <>
                  🔄 Processing: {progressInfo.current}/{progressInfo.total}
                  {progressInfo.current_track && (
                    <div className="text-xs mt-1 opacity-75">
                      Current: {progressInfo.current_track}
                    </div>
                  )}
                </>
              )}
            </p>
          </div>
        )}

        <div className="space-y-2">
          <button
            onClick={scanLibrary}
            disabled={scanLoading || processLoading}
            className="w-full px-3 py-2 text-sm bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scanLoading ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Scanning Library...
              </div>
            ) : (
              '📖 Scan Library'
            )}
          </button>

          <button
            onClick={processEmbeddings}
            disabled={processLoading || scanLoading}
            className="w-full px-3 py-2 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-lg hover:bg-green-200 dark:hover:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {processLoading ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processing Embeddings...
              </div>
            ) : (
              '⚡ Process Embeddings'
            )}
          </button>

          {processLoading && (
            <button
              onClick={stopProcessing}
              className="w-full px-3 py-2 text-sm bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-800"
            >
              🛑 Stop Processing
            </button>
          )}
        </div>

        <div className="mt-3 text-xs text-gray-500 dark:text-gray-400">
          <p>• Scan Library: Discovers tracks and saves metadata</p>
          <p>• Process Embeddings: Generates AI embeddings for search</p>
          <p>• Processing can be stopped and resumed anytime</p>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              ⚠️ No Client Workers Available
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-6">
              No GPU workers are currently connected to process embeddings. Processing on the server may be very slow if it lacks sufficient hardware (GPU/powerful CPU).
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              To use GPU workers, start a client with: <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">mycelium client --server-host your-server-ip</code>
            </p>
            <div className="flex space-x-3">
              <button
                onClick={processOnServer}
                className="flex-1 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
              >
                🖥️ Process on Server
              </button>
              <button
                onClick={cancelConfirmation}
                className="flex-1 px-4 py-2 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-400 dark:hover:bg-gray-500"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
