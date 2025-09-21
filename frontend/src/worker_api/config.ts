// Worker API configuration
const getWorkerApiBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = process.env.NEXT_PUBLIC_WORKER_API_PORT || '8001';
    return `${protocol}//${hostname}:${port}`;
  }
  return 'http://localhost:8001';
};

export const WORKER_API_BASE_URL = getWorkerApiBaseUrl();
