'use client';

import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';
import { useProcessing } from '../contexts/ProcessingContext';

interface Track {
  id: string;
  artist: string;
  album: string;
  title: string;
  filepath: string;
  plex_rating_key: string;
}

interface TrackResponse {
  artist: string;
  album: string;
  title: string;
  filepath: string;
  plex_rating_key: string;
}

interface LibrarySearchResult {
  track: Track;
  similarity_score: number;
  distance: number;
}

interface ProcessingTask {
  taskId: string;
  trackId: string;
  startTime: number;
}

export default function LibraryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredTracks, setFilteredTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [recommendations, setRecommendations] = useState<LibrarySearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [processingState, setProcessingState] = useState<'none' | 'worker' | 'server'>('none');
  const [currentTask, setCurrentTask] = useState<ProcessingTask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null);
  
  // Advanced search state
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [artistSearch, setArtistSearch] = useState('');
  const [albumSearch, setAlbumSearch] = useState('');
  const [titleSearch, setTitleSearch] = useState('');
  const [numResults, setNumResults] = useState(10);

    const {
    fetchStats,
    fetchProgress
  } = useProcessing();

  const fetchTracks = useCallback(async (searchTerm?: string) => {
    setLoading(true);
    setError(null);
    try {
      let url = `${API_BASE_URL}/api/library/tracks?page=1&limit=100`;
      if (searchTerm && searchTerm.trim()) {
        url += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }
      
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to fetch tracks');
      }
      const data = await response.json();
      
      // Convert API response to Track objects
      const tracksData: Track[] = data.tracks.map((track: TrackResponse) => ({
        id: track.plex_rating_key,
        artist: track.artist,
        album: track.album,
        title: track.title,
        filepath: track.filepath,
        plex_rating_key: track.plex_rating_key,
        processed: false // We'll determine this based on embeddings
      }));
      
      setFilteredTracks(tracksData);
    } catch (err) {
      console.error('Error fetching tracks:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch tracks');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTracksAdvanced = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `${API_BASE_URL}/api/library/tracks?page=1&limit=100`;
      
      // Add advanced search parameters
      const params = new URLSearchParams();
      if (artistSearch.trim()) {
        params.append('artist', artistSearch.trim());
      }
      if (albumSearch.trim()) {
        params.append('album', albumSearch.trim());
      }
      if (titleSearch.trim()) {
        params.append('title', titleSearch.trim());
      }
      
      if (params.toString()) {
        url += `&${params.toString()}`;
      }
      
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to fetch tracks');
      }
      const data = await response.json();
      
      // Convert API response to Track objects
      const tracksData: Track[] = data.tracks.map((track: TrackResponse) => ({
        id: track.plex_rating_key,
        artist: track.artist,
        album: track.album,
        title: track.title,
        filepath: track.filepath,
        plex_rating_key: track.plex_rating_key,
        processed: false // We'll determine this based on embeddings
      }));
      
      setFilteredTracks(tracksData);
    } catch (err) {
      console.error('Error fetching tracks:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch tracks');
    } finally {
      setLoading(false);
    }
  }, [artistSearch, albumSearch, titleSearch]);

  useEffect(() => {
    // Only setup cleanup for polling on unmount, don't auto-fetch tracks
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [pollInterval]);

  useEffect(() => {
    // Trigger search when any search field changes
    if (showAdvancedSearch && (artistSearch.trim() || albumSearch.trim() || titleSearch.trim())) {
      // Use advanced search when enabled AND at least one field has content
      fetchTracksAdvanced();
    } else if (!showAdvancedSearch && searchQuery.trim()) {
      // Use simple search when enabled AND search query has content
      fetchTracks(searchQuery);
    } else {
      // No active search - clear the tracks to show empty state
      setFilteredTracks([]);
    }
    // Note: No auto-fetch when no search is active - show empty state instead
  }, [searchQuery, showAdvancedSearch, artistSearch, albumSearch, titleSearch, fetchTracks, fetchTracksAdvanced]);

  const pollTaskStatus = async (taskId: string): Promise<boolean> => {
    try {
      console.log(`Polling task status for task_id: ${taskId}`);
      const response = await fetch(`${API_BASE_URL}/api/queue/task/${taskId}`);
      if (response.ok) {
        const taskStatus = await response.json();
        console.log(`Task status response:`, taskStatus);
        
        if (taskStatus.status === 'success') {
          console.log(`Task ${taskId} completed successfully`);
          return true; // Task completed successfully
        } else if (taskStatus.status === 'failed') {
          console.error(`Task ${taskId} failed:`, taskStatus.error_message);
          setError(`Processing failed: ${taskStatus.error_message || 'Unknown error'}`);
          return false;
        }
        console.log(`Task ${taskId} still in progress, status: ${taskStatus.status}`);
        // Still in progress, continue polling
        return false;
      } else {
        console.warn(`Task status request failed with status ${response.status}, assuming task completed`);
        // Task not found or error - assume it completed
        return true;
      }
    } catch (err) {
      console.error('Error polling task status:', err);
      // On error, assume completed and try to get recommendations
      return true;
    }
  };

  const startTaskPolling = async (taskId: string, trackId: string, track: Track) => {
    console.log(`Starting task polling for task_id: ${taskId}, track_id: ${trackId}`);
    
    // Clear any existing polling
    if (pollInterval) {
      clearInterval(pollInterval);
    }

    const task: ProcessingTask = {
      taskId,
      trackId,
      startTime: Date.now()
    };
    setCurrentTask(task);
    setProcessingState('worker');

    const interval = setInterval(async () => {
      const completed = await pollTaskStatus(taskId);
      
      if (completed) {
        console.log(`Task ${taskId} completed, clearing polling and retrying recommendations`);
        clearInterval(interval);
        setPollInterval(null);
        setCurrentTask(null);
        setProcessingState('none');
        
        // Wait a moment for the embedding to be fully saved
        setTimeout(() => {
          console.log(`Retrying recommendations for track after task completion`);
          // Automatically retry getting recommendations
          getRecommendations(track, true);
        }, 1000);
      }
      
      // Stop polling after 5 minutes to prevent infinite polling
      const elapsed = Date.now() - task.startTime;
      if (elapsed > 300000) {
        console.warn(`Task ${taskId} polling timeout after ${elapsed}ms`);
        clearInterval(interval);
        setPollInterval(null);
        setCurrentTask(null);
        setProcessingState('none');
        setError('Processing took too long. Please try clicking the track again.');
      }
    }, 2000); // Poll every 2 seconds
    
    setPollInterval(interval);
  };

  const getRecommendations = async (track: Track, isRetry: boolean = false) => {
    if (!isRetry) {
      setRecommendationsLoading(true);
      setRecommendations([]);
      setError(null);
      setProcessingState('none');
      setCurrentTask(null);
    }
    
    try {
      // Use the correct similar tracks endpoint
      const response = await fetch(`${API_BASE_URL}/similar/by_track/${track.plex_rating_key}?n_results=${numResults}`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Check if it's a list of results or a confirmation required response
        if (Array.isArray(data)) {
          setRecommendations(data);
          setRecommendationsLoading(false);
          await fetchStats();
          await fetchProgress();
        } else if (data.status === 'confirmation_required') {
          // Handle confirmation required case - offer processing options
          const shouldProcess = window.confirm(
            `This track needs to be processed first.\n\nWould you like to process it now?`
          );
          
          if (shouldProcess) {
            setProcessingState('server');
            try {
              // Try to process on server (now synchronous)
              const processResponse = await fetch(`${API_BASE_URL}/compute/on_server`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ track_id: track.plex_rating_key })
              });
              
              if (processResponse.ok) {
                  setProcessingState('none');
                  await getRecommendations(track, true);
              } else {
                const errorData = await processResponse.json().catch(() => ({}));
                setError(errorData.detail || 'Failed to process track. Please try again later.');
              }
            } catch {
              setError('Error processing track. Please check your connection.');
            } finally {
              setProcessingState('none');
            }
          } else {
            setRecommendationsLoading(false);
          }
        } else if (data.status === 'processing') {
          // Handle worker processing case - start polling immediately
          if (!isRetry && data.task_id) {
            console.log('Starting worker processing with task_id:', data.task_id);
            // Immediately set processing state to show worker processing UI
            setRecommendationsLoading(false);
            startTaskPolling(data.task_id, track.plex_rating_key, track);
          } else if (!data.task_id) {
            console.error('Worker processing response missing task_id:', data);
            setError('Worker processing started but missing task ID. Please try again.');
            setRecommendationsLoading(false);
          }
        } else {
          console.error('Unexpected response from server:', data);
          setError(`Unexpected response from server: ${data.status || 'unknown status'}. Please try again.`);
          setRecommendationsLoading(false);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        setError(errorData.detail || 'Failed to get recommendations. Please try again.');
        setRecommendationsLoading(false);
      }
    } catch (err) {
      console.error('Failed to get recommendations:', err);
      setError('Error connecting to server. Please check your connection.');
      setRecommendationsLoading(false);
      setProcessingState('none');
    }
  };

  const handleTrackSelect = (track: Track) => {
    // Clear any existing polling when selecting a new track
    if (pollInterval) {
      clearInterval(pollInterval);
      setPollInterval(null);
    }
    
    setSelectedTrack(track);
    setCurrentTask(null);
    setProcessingState('none');
    getRecommendations(track);
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="p-6 border-b border-gray-200 dark:border-gray-600">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          📚 Music Library
        </h2>
        <p className="text-gray-600 dark:text-gray-300 mb-4">
          Search your Plex music library and get recommendations based on specific tracks.
        </p>
        
        {/* Search Interface */}
        <div className="space-y-4">
          {/* Search Type Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => {
                  setShowAdvancedSearch(false);
                  // Clear advanced search fields when switching to simple search
                  setArtistSearch('');
                  setAlbumSearch('');
                  setTitleSearch('');
                }}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  !showAdvancedSearch
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                Simple Search
              </button>
              <button
                onClick={() => {
                  setShowAdvancedSearch(true);
                  // Clear simple search when switching to advanced search
                  setSearchQuery('');
                }}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  showAdvancedSearch
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                Advanced Search
              </button>
            </div>
          </div>

          {/* Simple Search */}
          {!showAdvancedSearch && (
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search artists, albums, or tracks..."
                className="w-full px-4 py-3 pl-10 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              <svg
                className="absolute left-3 top-3.5 h-5 w-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          )}

          {/* Advanced Search */}
          {showAdvancedSearch && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Artist
                  </label>
                  <input
                    type="text"
                    value={artistSearch}
                    onChange={(e) => setArtistSearch(e.target.value)}
                    placeholder="Search by artist..."
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Album
                  </label>
                  <input
                    type="text"
                    value={albumSearch}
                    onChange={(e) => setAlbumSearch(e.target.value)}
                    placeholder="Search by album..."
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Title
                  </label>
                  <input
                    type="text"
                    value={titleSearch}
                    onChange={(e) => setTitleSearch(e.target.value)}
                    placeholder="Search by title..."
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                💡 Advanced search uses AND logic - tracks must match all specified criteria
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
        {/* Track List */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Your Tracks
          </h3>
          
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse bg-gray-200 dark:bg-gray-700 h-16 rounded-lg"></div>
              ))}
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">⚠️</div>
              <p className="text-red-600 dark:text-red-400 font-medium mb-2">
                {error}
              </p>
              <button
                onClick={() => fetchTracks()}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                Retry
              </button>
            </div>
          ) : filteredTracks.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">🔍</div>
              <p className="text-gray-500 dark:text-gray-400 mb-2">
                {(searchQuery || (showAdvancedSearch && (artistSearch.trim() || albumSearch.trim() || titleSearch.trim()))) ? 'No tracks found matching your search' : 'Start searching to find your tracks'}
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500">
                {!(searchQuery || (showAdvancedSearch && (artistSearch.trim() || albumSearch.trim() || titleSearch.trim()))) ? 'Use the search bar above to explore your music library' : 'Try different search terms or scan your Plex library first'}
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filteredTracks.map((track) => (
                <button
                  key={track.id}
                  onClick={() => handleTrackSelect(track)}
                  className={`w-full p-3 text-left rounded-lg border transition-colors ${
                    selectedTrack?.id === track.id
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-purple-300 dark:hover:border-purple-500'
                  }`}
                >
                  <div className="font-medium text-gray-900 dark:text-white">
                    {track.title}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-300">
                    {track.artist} • {track.album}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Recommendations */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Recommendations
            </h3>
            {selectedTrack && (
              <div className="flex items-center space-x-2">
                <label htmlFor="rec-num-results" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Results:
                </label>
                <input
                  id="rec-num-results"
                  type="number"
                  min="1"
                  max="50"
                  value={numResults}
                  onChange={(e) => {
                    const newValue = Math.max(1, Math.min(50, parseInt(e.target.value) || 10));
                    setNumResults(newValue);
                    // Re-fetch recommendations with new count if we have a selected track and no processing is happening
                    if (selectedTrack && processingState === 'none' && !recommendationsLoading) {
                      getRecommendations(selectedTrack);
                    }
                  }}
                  className="w-16 px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            )}
          </div>
          
          {!selectedTrack ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">👆</div>
              <p className="text-gray-500 dark:text-gray-400">
                Select a track to see recommendations
              </p>
            </div>
          ) : recommendationsLoading || processingState !== 'none' ? (
            <div className="space-y-3">
              <div className="text-center py-4">
                {processingState === 'worker' && currentTask ? (
                  <div>
                    <div className="text-2xl mb-2">⚙️</div>
                    <p className="text-blue-600 dark:text-blue-400 font-medium">
                      Processing with AI worker...
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      This will complete automatically when ready
                    </p>
                  </div>
                ) : processingState === 'server' ? (
                  <div>
                    <div className="text-2xl mb-2">🖥️</div>
                    <p className="text-purple-600 dark:text-purple-400 font-medium">
                      Processing on server...
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      Computing audio signature
                    </p>
                  </div>
                ) : (
                  <div>
                    <div className="text-2xl mb-2">🔍</div>
                    <p className="text-gray-600 dark:text-gray-400 font-medium">
                      Finding similar tracks...
                    </p>
                  </div>
                )}
              </div>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse bg-gray-200 dark:bg-gray-700 h-16 rounded-lg"></div>
              ))}
            </div>
          ) : recommendations.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">🔍</div>
              <p className="text-gray-500 dark:text-gray-400">
                No recommendations found
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                Make sure embeddings are processed
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {recommendations.map((result, index) => (
                <div
                  key={index}
                  className="p-3 border border-gray-200 dark:border-gray-600 rounded-lg"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {result.track.title}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-300">
                        {result.track.artist} • {result.track.album}
                      </div>
                    </div>
                    <div className="text-sm text-purple-600 dark:text-purple-400 font-medium">
                      {(result.similarity_score * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}