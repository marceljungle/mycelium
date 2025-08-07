// API configuration
const getApiBaseUrl = (): string => {
  // Check if we're in the browser
  if (typeof window !== 'undefined') {
    // Try to get from environment variable first
    const envApiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envApiUrl) {
      return envApiUrl;
    }

    // Fallback: use the current host with API port
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const apiPort = process.env.NEXT_PUBLIC_API_PORT || '8000';

    return `${protocol}//${hostname}:${apiPort}`;
  }

  // Server-side fallback
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

export const API_BASE_URL = getApiBaseUrl();

export const API_ENDPOINTS = {
  SEARCH_TEXT: `${API_BASE_URL}/api/search/text`,
  LIBRARY_STATS: `${API_BASE_URL}/api/library/stats`,
} as const;
