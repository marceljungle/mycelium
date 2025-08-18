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
  
  // Processing state
  const [processLoading, setProcessLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
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
    } catch {
      // Ignore progress fetch errors
    }
  }, [stats, processLoading, operationMessage]);

  const scanLibrary = useCallback(async () => {
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
    } catch {
      setOperationMessage('❌ Failed to scan library. Make sure the API server is running and Plex is accessible.');
    } finally {
      setScanLoading(false);
    }
  }, [fetchStats, fetchProgress]);

  const processEmbeddings = useCallback(async () => {
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

    } catch {
      setOperationMessage('❌ Failed to start processing. Make sure the API server is running.');
      setProcessLoading(false);
      setProgressInfo(null);
    }
  }, []);

  const processOnServer = useCallback(async () => {
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

    } catch {
      setOperationMessage('❌ Failed to start server processing. Make sure the API server is running.');
      setProcessLoading(false);
      setProgressInfo(null);
    }
  }, []);

  const stopProcessing = useCallback(async () => {
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
    } catch {
      setOperationMessage('❌ Failed to send stop signal.');
    }
  }, []);

  const cancelConfirmation = useCallback(() => {
    setShowConfirmation(false);
    setOperationMessage(null);
  }, []);

  // Auto-refresh stats and progress
  useEffect(() => {
    fetchStats();
    fetchProgress();

    // Refresh stats and progress every 5 seconds
    const interval = setInterval(() => {
      fetchStats();
      fetchProgress();
    }, 5000);

    return () => clearInterval(interval);
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
    setOperationMessage,
  };

  return (
    <ProcessingContext.Provider value={value}>
      {children}
    </ProcessingContext.Provider>
  );
}