// API configuration
const getApiBaseUrl = (): string => {
  // Check if we're in the browser
  if (typeof window !== 'undefined') {

    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    let apiPort;

    if (process.env.NEXT_PUBLIC_API_PORT) {
        apiPort = process.env.NEXT_PUBLIC_API_PORT;
    } else {
        if (isClientMode()) {
            apiPort = '8001'; // Default port for client mode
        } else {
            apiPort = '8000'; // Default port for server mode
        }
    }

    apiPort = process.env.NEXT_PUBLIC_API_PORT || '8000';

    return `${protocol}//${hostname}:${apiPort}`;
  }

  // Server-side fallback
  return 'http://localhost:8000';
};

// Check if running in client mode
const isClientMode = (): boolean => {
  return process.env.NEXT_PUBLIC_MYCELIUM_MODE === 'client';
};

export const API_BASE_URL = getApiBaseUrl();

export const IS_CLIENT_MODE = isClientMode();

export const API_ENDPOINTS = {
  SEARCH_TEXT: `${API_BASE_URL}/api/search/text`,
  LIBRARY_STATS: `${API_BASE_URL}/api/library/stats`,
} as const;

// Worker API configuration (client/worker runtime)
export const WORKER_API_BASE_URL = (() => {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = process.env.NEXT_PUBLIC_WORKER_API_PORT || '8001';
    return `${protocol}//${hostname}:${port}`;
  }
  return 'http://localhost:8001';
})();
