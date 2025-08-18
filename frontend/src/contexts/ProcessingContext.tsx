'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
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

interface ProcessingContextType {
  // Library stats
  stats: LibraryStats | null;
  statsLoading: boolean;
  statsError: string | null;
  
  // Processing state
  processLoading: boolean;
  scanLoading: boolean;
  operationMessage: string | null;
  progressInfo: ProgressInfo | null;
  showConfirmation: boolean;
  
  // Actions
  fetchStats: () => Promise<void>;
  fetchProgress: () => Promise<void>;
  scanLibrary: () => Promise<void>;
  processEmbeddings: () => Promise<void>;
  processOnServer: () => Promise<void>;
  stopProcessing: () => Promise<void>;
  cancelConfirmation: () => void;
  setOperationMessage: (message: string | null) => void;
}

const ProcessingContext = createContext<ProcessingContextType | undefined>(undefined);

export function useProcessing() {
  const context = useContext(ProcessingContext);
  if (context === undefined) {
    throw new Error('useProcessing must be used within a ProcessingProvider');
  }
  return context;
}

interface ProcessingProviderProps {
  children: React.ReactNode;
}

export function ProcessingProvider({ children }: ProcessingProviderProps) {
  // Library stats state
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  
  // Processing state - initialize from localStorage
  const [processLoading, setProcessLoading] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mycelium_processLoading') === 'true';
    }
    return false;
  });
  const [scanLoading, setScanLoading] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mycelium_scanLoading') === 'true';
    }
    return false;
  });
  const [operationMessage, setOperationMessage] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mycelium_operationMessage');
    }
    return null;
  });
  const [progressInfo, setProgressInfo] = useState<ProgressInfo | null>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('mycelium_progressInfo');
      return stored ? JSON.parse(stored) : null;
    }
    return null;
  });
  const [showConfirmation, setShowConfirmation] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('mycelium_showConfirmation') === 'true';
    }
    return false;
  });

  // Wrapper functions to persist state changes to localStorage
  const persistentSetProcessLoading = useCallback((value: boolean) => {
    setProcessLoading(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem('mycelium_processLoading', String(value));
    }
  }, []);

  const persistentSetScanLoading = useCallback((value: boolean) => {
    setScanLoading(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem('mycelium_scanLoading', String(value));
    }
  }, []);

  const persistentSetOperationMessage = useCallback((value: string | null) => {
    setOperationMessage(value);
    if (typeof window !== 'undefined') {
      if (value === null) {
        localStorage.removeItem('mycelium_operationMessage');
      } else {
        localStorage.setItem('mycelium_operationMessage', value);
      }
    }
  }, []);

  const persistentSetProgressInfo = useCallback((value: ProgressInfo | null) => {
    setProgressInfo(value);
    if (typeof window !== 'undefined') {
      if (value === null) {
        localStorage.removeItem('mycelium_progressInfo');
      } else {
        localStorage.setItem('mycelium_progressInfo', JSON.stringify(value));
      }
    }
  }, []);

  const persistentSetShowConfirmation = useCallback((value: boolean) => {
    setShowConfirmation(value);
    if (typeof window !== 'undefined') {
      localStorage.setItem('mycelium_showConfirmation', String(value));
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/stats`);
      if (!response.ok) {
        throw new Error('Failed to fetch library stats');
      }
      const data = await response.json();
      setStats(data);
      setStatsError(null);
    } catch {
      setStatsError('Unable to connect to API');
      setStats(null);
    } finally {
      setStatsLoading(false);
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
          persistentSetProcessLoading(true);
          persistentSetProgressInfo({ stage: 'processing' });
        } else if (!data.is_processing && processLoading && !operationMessage?.includes('Stop signal sent')) {
          persistentSetProcessLoading(false);
          persistentSetProgressInfo(null);
          if (operationMessage?.includes('started')) {
            persistentSetOperationMessage('✅ Processing completed! Check the progress above for details.');
          }
        }
      }
    } catch {
      // Ignore progress fetch errors
    }
  }, [stats, processLoading, operationMessage, persistentSetProcessLoading, persistentSetProgressInfo, persistentSetOperationMessage]);

  const scanLibrary = useCallback(async () => {
    persistentSetScanLoading(true);
    persistentSetOperationMessage(null);
    persistentSetProgressInfo(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/scan`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to scan library');
      }
      const data = await response.json();
      persistentSetOperationMessage(
        `✅ Scan completed! Found ${data.total_tracks} total tracks ` +
        `(${data.new_tracks} new, ${data.updated_tracks} updated)`
      );
      // Refresh stats after scanning
      await fetchStats();
      await fetchProgress();
    } catch {
      persistentSetOperationMessage('❌ Failed to scan library. Make sure the API server is running and Plex is accessible.');
    } finally {
      persistentSetScanLoading(false);
    }
  }, [fetchStats, fetchProgress, persistentSetScanLoading, persistentSetOperationMessage, persistentSetProgressInfo]);

  const processEmbeddings = useCallback(async () => {
    persistentSetProcessLoading(true);
    persistentSetOperationMessage(null);
    persistentSetProgressInfo({ stage: 'starting' });

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start processing');
      }
      const data = await response.json();

      if (data.status === 'already_running') {
        persistentSetOperationMessage('⚠️ Processing is already in progress');
        persistentSetProcessLoading(false);
        persistentSetProgressInfo(null);
        return;
      }

      if (data.status === 'worker_processing_started') {
        persistentSetOperationMessage(`🚀 Worker processing started! Created ${data.tasks_created} tasks for ${data.active_workers} workers. Progress will be updated automatically.`);
        // Don't set processLoading to false - let the progress monitoring handle it
        return;
      }

      if (data.status === 'no_workers' && data.confirmation_required) {
        persistentSetOperationMessage('⚠️ No client workers detected. Server processing will use local hardware.');
        persistentSetShowConfirmation(true);
        persistentSetProcessLoading(false);
        persistentSetProgressInfo(null);
        return;
      }

      // Handle other status types
      if (data.status === 'server_started') {
        persistentSetOperationMessage('🚀 Server processing started! Progress will be updated automatically.');
        return;
      }

      // Default success case (backward compatibility)
      persistentSetOperationMessage('🚀 Processing started! Progress will be updated automatically.');

    } catch {
      persistentSetOperationMessage('❌ Failed to start processing. Make sure the API server is running.');
      persistentSetProcessLoading(false);
      persistentSetProgressInfo(null);
    }
  }, [persistentSetProcessLoading, persistentSetOperationMessage, persistentSetProgressInfo, persistentSetShowConfirmation]);

  const processOnServer = useCallback(async () => {
    persistentSetProcessLoading(true);
    persistentSetShowConfirmation(false);
    persistentSetOperationMessage(null);
    persistentSetProgressInfo({ stage: 'starting' });

    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process/server`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to start server processing');
      }
      const data = await response.json();

      if (data.status === 'already_running') {
        persistentSetOperationMessage('⚠️ Processing is already in progress');
        persistentSetProcessLoading(false);
        persistentSetProgressInfo(null);
        return;
      }

      persistentSetOperationMessage('🖥️ Server processing started! This may take longer on low-power hardware. Progress will be updated automatically.');

    } catch {
      persistentSetOperationMessage('❌ Failed to start server processing. Make sure the API server is running.');
      persistentSetProcessLoading(false);
      persistentSetProgressInfo(null);
    }
  }, [persistentSetProcessLoading, persistentSetShowConfirmation, persistentSetOperationMessage, persistentSetProgressInfo]);

  const stopProcessing = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/process/stop`, {
        method: 'POST',
      });
      if (response.ok) {
        // Clear progress info and processing state immediately when stop is requested
        persistentSetProgressInfo(null);
        persistentSetProcessLoading(false);
        persistentSetOperationMessage('🛑 Stop signal sent. Processing will finish current track and stop.');
      }
    } catch {
      persistentSetOperationMessage('❌ Failed to send stop signal.');
    }
  }, [persistentSetProgressInfo, persistentSetProcessLoading, persistentSetOperationMessage]);

  const cancelConfirmation = useCallback(() => {
    persistentSetShowConfirmation(false);
    persistentSetOperationMessage(null);
  }, [persistentSetShowConfirmation, persistentSetOperationMessage]);

  // Auto-refresh stats and progress
  useEffect(() => {
    fetchStats();
    fetchProgress();

    // Refresh stats and progress every 5 seconds
    const interval = setInterval(() => {
      fetchStats();
      fetchProgress();
    }, 5000);

    // Cleanup function to clear localStorage on unmount (optional - you might want to keep state)
    return () => {
      clearInterval(interval);
      // Uncomment these lines if you want to clear state on app close:
      // localStorage.removeItem('mycelium_processLoading');
      // localStorage.removeItem('mycelium_scanLoading');
      // localStorage.removeItem('mycelium_operationMessage');
      // localStorage.removeItem('mycelium_progressInfo');
      // localStorage.removeItem('mycelium_showConfirmation');
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value: ProcessingContextType = {
    // Library stats
    stats,
    statsLoading,
    statsError,
    
    // Processing state
    processLoading,
    scanLoading,
    operationMessage,
    progressInfo,
    showConfirmation,
    
    // Actions
    fetchStats,
    fetchProgress,
    scanLibrary,
    processEmbeddings,
    processOnServer,
    stopProcessing,
    cancelConfirmation,
    setOperationMessage: persistentSetOperationMessage,
  };

  return (
    <ProcessingContext.Provider value={value}>
      {children}
    </ProcessingContext.Provider>
  );
}