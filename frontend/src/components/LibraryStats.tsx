'use client';

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

interface LibraryStats {
  total_embeddings: number;
  collection_name: string;
  database_path: string;
}

export default function LibraryStats() {
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [processLoading, setProcessLoading] = useState(false);
  const [operationMessage, setOperationMessage] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/stats`);
      if (!response.ok) {
        throw new Error('Failed to fetch library stats');
      }
      const data = await response.json();
      setStats(data);
      setError(null);
    } catch (err) {
      setError('Unable to connect to API');
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const scanLibrary = async () => {
    setScanLoading(true);
    setOperationMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/scan`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to scan library');
      }
      const data = await response.json();
      setOperationMessage(`✅ ${data.message}. Found ${data.tracks_found} tracks.`);
      // Refresh stats after scanning
      await fetchStats();
    } catch (err) {
      setOperationMessage('❌ Failed to scan library. Make sure the API server is running.');
    } finally {
      setScanLoading(false);
    }
  };

  const processLibrary = async () => {
    setProcessLoading(true);
    setOperationMessage(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to process library');
      }
      const data = await response.json();
      setOperationMessage(`✅ ${data.message}`);
      // Refresh stats after processing
      await fetchStats();
    } catch (err) {
      setOperationMessage('❌ Failed to process library. This operation may take a while or require more resources.');
    } finally {
      setProcessLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

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

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📊 Library Statistics
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
          <div className="bg-gradient-to-r from-purple-100 to-pink-100 dark:from-purple-900 dark:to-pink-900 p-4 rounded-lg">
            <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
              {stats.total_embeddings.toLocaleString()}
            </div>
            <div className="text-sm text-purple-700 dark:text-purple-300">
              Total Tracks Indexed
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
          
          <div className="pt-4 border-t border-gray-200 dark:border-gray-600">
            <button
              onClick={fetchStats}
              className="w-full px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"
            >
              🔄 Refresh Stats
            </button>
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
      
      {/* Quick Actions */}
      <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-600">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
          Quick Actions
        </h4>

        {operationMessage && (
          <div className="mb-3 p-3 bg-blue-50 dark:bg-blue-900/50 border border-blue-200 dark:border-blue-700 rounded-lg">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              {operationMessage}
            </p>
          </div>
        )}

        <div className="space-y-2">
          <button
            onClick={scanLibrary}
            disabled={scanLoading}
            className="w-full px-3 py-2 text-sm bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scanLoading ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Scanning...
              </div>
            ) : (
              '📖 Scan Library'
            )}
          </button>
          <button
            onClick={processLibrary}
            disabled={processLoading}
            className="w-full px-3 py-2 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-lg hover:bg-green-200 dark:hover:bg-green-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {processLoading ? (
              <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24"></svg>
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </div>
            ) : (
              '⚡ Process Library'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
