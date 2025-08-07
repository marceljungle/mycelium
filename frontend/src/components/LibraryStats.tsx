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
        <div className="space-y-2">
          <button className="w-full px-3 py-2 text-sm bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg hover:bg-blue-200 dark:hover:bg-blue-800">
            📖 Scan Library
          </button>
          <button className="w-full px-3 py-2 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded-lg hover:bg-green-200 dark:hover:bg-green-800">
            ⚡ Process Library
          </button>
        </div>
      </div>
    </div>
  );
}