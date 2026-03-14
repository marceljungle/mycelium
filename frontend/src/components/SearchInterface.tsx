'use client';

import { useState, useRef, useEffect } from 'react';
import SearchResults from './SearchResults';
import { api } from '@/server_api/client';
import type { SearchResultResponse, CapabilitiesResponse } from '@/server_api/generated/models';

export default function SearchInterface() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<'text' | 'audio'>('audio');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [numResults, setNumResults] = useState(10);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Model capabilities
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  
  // Worker processing state
  const [processingState, setProcessingState] = useState<'none' | 'worker' | 'server'>('none');
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);

  // Fetch capabilities on mount
  useEffect(() => {
    api.getCapabilities().then((caps) => {
      setCapabilities(caps);
      // Default to text search only if supported
      if (caps.supports_text_search) {
        setSearchType('text');
      } else {
        setSearchType('audio');
      }
    }).catch(() => {
      // Fallback: assume all capabilities
      setSearchType('text');
    });
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [pollInterval]);

  const pollTaskStatus = async (taskId: string): Promise<boolean> => {
    try {
      const taskData = await api.getTaskStatus({ taskId });
      if (taskData) {
        console.log(`Polling task ${taskId}: status=${taskData.status}, has_results=${!!taskData.search_results}`);

        if (taskData.status === 'success' && taskData.search_results) {
          // Task completed successfully with search results
          console.log(`Task ${taskId} completed successfully with ${taskData.search_results.length} results`);
          setResults(taskData.search_results);
          return true;
        } else if (taskData.status === 'failed') {
          // Task failed
          console.error(`Task ${taskId} failed:`, taskData.error_message);
          setError(taskData.error_message || 'Search task failed on worker');
          return true;
        } else if (taskData.status === 'success' && !taskData.search_results) {
          // Task marked as success but no results yet - this might be a race condition
          console.warn(`Task ${taskId} marked as success but no search results yet, continuing polling...`);
          return false;
        }
        // Task still in progress
        console.log(`Task ${taskId} still in progress (status: ${taskData.status})`);
        return false;
      } else {
        return false;
      }
    } catch (error) {
      console.error('Error polling task status:', error);
      return false;
    }
  };

  const startTaskPolling = (taskId: string) => {
    console.log('Starting task polling for search task:', taskId);
    setProcessingState('worker');

    let pollCount = 0;
    const maxPolls = 150; // 5 minutes with 2-second intervals

    const interval = setInterval(async () => {
      pollCount++;
      const completed = await pollTaskStatus(taskId);
      
      if (completed) {
        console.log(`Search task ${taskId} completed, clearing polling after ${pollCount} polls`);
        clearInterval(interval);
        setPollInterval(null);
        setProcessingState('none');
        setLoading(false);
        setAudioLoading(false);
      } else if (pollCount >= maxPolls) {
        console.warn(`Search task ${taskId} polling timeout after ${pollCount} polls (${maxPolls * 2} seconds)`);
        clearInterval(interval);
        setPollInterval(null);
        setProcessingState('none');
        setLoading(false);
        setAudioLoading(false);
        setError('Search task timed out. Please try again.');
      }
    }, 2000); // Poll every 2 seconds

    setPollInterval(interval);
  };

  const handleTextSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.searchText({ q: query, nResults: numResults });
      
      // Check if it's direct search results or a processing response
      if (Array.isArray(data)) {
        // Direct search results (server processed immediately)
        setResults(data);
        setLoading(false);


      } else if (data.status === 'processing') {
        // Worker processing - start polling
        if (data.task_id) {
          console.log('Text search sent to worker, starting polling for task:', data.task_id);
          startTaskPolling(data.task_id);
        } else {
          console.error('Processing response missing taskId for text search');
          setError('Worker processing started but no task ID was returned.');
          setLoading(false);
        }
      } else if (data.status === 'confirmation_required') {
        // No workers available - ask for confirmation
        const shouldProcess = window.confirm(
          `Text search requires embedding computation, and no workers are active.\n\nWould you like to process it on the server?`
        );
        
        if (shouldProcess) {
          setProcessingState('server');
          try {
            // Process on server
            const serverResults = await api.computeTextSearch({ computeTextSearchRequest: { query, n_results: numResults } });
            setResults(serverResults);
          } catch {
            setError('Error processing text search on server. Please check your connection.');
          } finally {
            setProcessingState('none');
            setLoading(false);
          }
        } else {
          setLoading(false);
        }
      } else {
        console.error('Unexpected response from text search:', data);
        setError(`Unexpected response from server: ${data.status || 'unknown status'}. Please try again.`);
        setLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setResults([]);
      setLoading(false);
    }
  };

  const handleAudioSearch = async () => {
    if (!audioFile) return;

    setAudioLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('audio', audioFile);
      formData.append('n_results', numResults.toString());

      const data = await api.searchAudio({ audio: audioFile, nResults: numResults });
      
      // Check if it's direct search results or a processing response
      if (Array.isArray(data)) {
        // Direct search results (server processed immediately)
        setResults(data);
        setAudioLoading(false);


      } else if (data.status === 'processing') {
        // Worker processing - start polling
        if (data.task_id) {
          console.log('Audio search sent to worker, starting polling for task:', data.task_id);
          startTaskPolling(data.task_id);
        } else {
          console.error('Processing response missing taskId for audio search');
          setError('Worker processing started but no task ID was returned.');
          setAudioLoading(false);
        }
      } else if (data.status === 'confirmation_required') {
        // No workers available - ask for confirmation
        const shouldProcess = window.confirm(
          `Audio search requires embedding computation, and no workers are active.\n\nWould you like to process it on the server?`
        );
        
        if (shouldProcess) {
          setProcessingState('server');
          try {
            const formData = new FormData();
            formData.append('audio', audioFile);
            formData.append('n_results', numResults.toString());

            const serverResults = await api.computeAudioSearch({ audio: audioFile, nResults: numResults });
            setResults(serverResults);
          } catch {
            setError('Error processing audio search on server. Please check your connection.');
          } finally {
            setProcessingState('none');
            setAudioLoading(false);
          }
        } else {
          setAudioLoading(false);
        }
      } else {
        console.error('Unexpected response from audio search:', data);
        setError(`Unexpected response from server: ${data.status || 'unknown status'}. Please try again.`);
        setAudioLoading(false);
      }
    } catch (err) {
      console.error('Audio search error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred during audio search');
      setResults([]);
      setAudioLoading(false);
    }
  };

  const validateAndSetFile = (file: File) => {
    // Check file type
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/flac', 'audio/ogg'];
    if (!validTypes.some(type => file.type.includes(type.split('/')[1]))) {
      setError('Please select a valid audio file (MP3, WAV, FLAC, or OGG)');
      return false;
    }

    setAudioFile(file);
    setError(null);
    return true;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && searchType === 'text') {
      handleTextSearch();
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      validateAndSetFile(file);
    }
  };

  const clearAudioFile = () => {
    setAudioFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
        🎵 Search Your Music
      </h2>
      
      {/* Search Type Toggle */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex space-x-1 bg-gray-100 dark:bg-gray-700 p-1 rounded-lg w-fit">
              {capabilities?.supports_text_search !== false && (
                <button
                  onClick={() => setSearchType('text')}
                  className={`px-4 py-2 rounded-md font-medium transition-colors ${
                    searchType === 'text'
                      ? 'bg-white dark:bg-gray-600 text-purple-600 dark:text-purple-400 shadow-sm'
                      : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
                  }`}
                >
                  📝 Text Search
                </button>
              )}
              <button
                onClick={() => setSearchType('audio')}
                className={`px-4 py-2 rounded-md font-medium transition-colors ${
                  searchType === 'audio'
                    ? 'bg-white dark:bg-gray-600 text-purple-600 dark:text-purple-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                🎧 Audio Search
              </button>
            </div>
            {capabilities && (
              <span className="text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
                {capabilities.embedding_model_type?.toUpperCase()}
              </span>
            )}
          </div>
          
          {/* Number of Results Control */}
          <div className="flex items-center space-x-2">
            <label htmlFor="num-results" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Results:
            </label>
            <input
              id="num-results"
              type="number"
              min="1"
              value={numResults}
              onChange={(e) => setNumResults(parseInt(e.target.value) || 10)}
              className="w-16 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Text Search */}
      {searchType === 'text' && (
        <div className="mb-6">
          <div className="flex gap-3">
            <div className="flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Describe the music you're looking for... (e.g., 'upbeat 80s synthpop', 'slow piano ballad', 'fast drumbeat with distorted guitar')"
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
              />
            </div>
            <button
              onClick={handleTextSearch}
              disabled={loading || processingState !== 'none' || !query.trim()}
              className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading || processingState !== 'none' ? (
                <div className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {processingState === 'worker' ? 'Processing with AI worker...' : 
                   processingState === 'server' ? 'Processing on server...' : 'Searching...'}
                </div>
              ) : (
                'Search'
              )}
            </button>
          </div>
          
          {/* Search suggestions */}
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              'upbeat 80s synthpop',
              'melancholic indie rock',
              'instrumental jazz trio',
              'electronic dance music',
              'acoustic folk ballad'
            ].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => setQuery(suggestion)}
                className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Audio Search */}
      {searchType === 'audio' && (
        <div className="mb-6">
          <div className="space-y-4">
            {/* File Upload Area */}
            <div 
              className={`border-2 border-dashed rounded-lg p-6 transition-colors ${
                isDragOver 
                  ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20' 
                  : 'border-gray-300 dark:border-gray-600'
              }`}
              onDragOver={handleDragOver}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileSelect}
                className="hidden"
                id="audio-upload"
              />
              
              {!audioFile ? (
                <label htmlFor="audio-upload" className="cursor-pointer">
                  <div className="text-center">
                    <svg className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <div className="mt-4">
                      <p className="text-lg font-medium text-gray-900 dark:text-white">
                        Drop audio file here or click to browse
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Supports MP3, WAV, FLAC, OGG
                      </p>
                    </div>
                  </div>
                </label>
              ) : (
                <div className="text-center">
                  <div className="flex items-center justify-center space-x-3">
                    <svg className="h-8 w-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"></path>
                    </svg>
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">
                        {audioFile.name}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {(audioFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                    <button
                      onClick={clearAudioFile}
                      className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Search Button for Audio */}
            <button
              onClick={handleAudioSearch}
              disabled={audioLoading || processingState !== 'none' || !audioFile}
              className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {audioLoading || processingState !== 'none' ? (
                <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {processingState === 'worker' ? 'Processing with AI worker...' : 
                   processingState === 'server' ? 'Processing on server...' : 'Analyzing Audio...'}
                </div>
              ) : (
                '🔍 Find Similar Music'
              )}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg">
          <p className="text-red-700 dark:text-red-300">
            <span className="font-medium">Error:</span> {error}
          </p>
          <p className="text-sm text-red-600 dark:text-red-400 mt-1">
            Make sure the Mycelium API server is running on localhost:8000
          </p>
        </div>
      )}

      <SearchResults results={results} loading={loading || audioLoading || processingState !== 'none'} />
    </div>
  );
}