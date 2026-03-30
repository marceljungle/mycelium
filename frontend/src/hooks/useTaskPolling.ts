'use client';

import { useEffect, useRef, useCallback } from 'react';
import { api } from '@/server_api/client';
import type { SearchResultResponse } from '@/server_api/client';

interface UseTaskPollingOptions {
  intervalMs?: number;
  maxPolls?: number;
}

interface UseTaskPollingReturn {
  startPolling: (taskId: string) => void;
  stopPolling: () => void;
  isPolling: boolean;
}

type OnSuccess = (taskId: string, results: SearchResultResponse[]) => void;
type OnError = (taskId: string, message: string) => void;
type OnTimeout = (taskId: string) => void;

export function useTaskPolling(
  onSuccess: OnSuccess,
  onError: OnError,
  onTimeout?: OnTimeout,
  options: UseTaskPollingOptions = {},
): UseTaskPollingReturn {
  const { intervalMs = 2000, maxPolls = 150 } = options;

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    isPollingRef.current = false;
  }, []);

  const startPolling = useCallback(
    (taskId: string) => {
      // Clear any previous interval
      stopPolling();
      isPollingRef.current = true;

      let pollCount = 0;

      const interval = setInterval(async () => {
        pollCount++;
        try {
          const taskData = await api.getTaskStatus({ taskId });
          if (!taskData) return;

          if (taskData.status === 'success' && taskData.search_results) {
            stopPolling();
            onSuccess(taskId, taskData.search_results);
            return;
          }

          if (taskData.status === 'success' && !taskData.search_results) {
            // Race condition: success but results not yet attached
            stopPolling();
            onSuccess(taskId, []);
            return;
          }

          if (taskData.status === 'failed') {
            stopPolling();
            onError(taskId, taskData.error_message || 'Task failed on worker');
            return;
          }
        } catch (err) {
          console.error('Polling error:', err);
        }

        if (pollCount >= maxPolls) {
          stopPolling();
          if (onTimeout) {
            onTimeout(taskId);
          } else {
            onError(taskId, 'Processing timed out. Please try again.');
          }
        }
      }, intervalMs);

      intervalRef.current = interval;
    },
    [intervalMs, maxPolls, onSuccess, onError, onTimeout, stopPolling],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    startPolling,
    stopPolling,
    isPolling: isPollingRef.current,
  };
}
