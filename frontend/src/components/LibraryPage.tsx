'use client';

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

interface Track {
  id: string;
  artist: string;
  album: string;
  title: string;
  filepath: string;
  plex_rating_key: string;
  processed: boolean;
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

export default function LibraryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [tracks, setTracks] = useState<Track[]>([]);
  const [filteredTracks, setFilteredTracks] = useState<Track[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [recommendations, setRecommendations] = useState<LibrarySearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTracks();
  }, []);

  useEffect(() => {
    // Filter tracks based on search query
    if (!searchQuery.trim()) {
      setFilteredTracks(tracks);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = tracks.filter(track =>
        track.artist.toLowerCase().includes(query) ||
        track.album.toLowerCase().includes(query) ||
        track.title.toLowerCase().includes(query)
      );
      setFilteredTracks(filtered);
    }
  }, [searchQuery, tracks]);

  const fetchTracks = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/library/tracks?page=1&limit=100`);
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
        processed: true // Assume processed if in the database
      }));
      
      setTracks(tracksData);
      setFilteredTracks(tracksData);
    } catch {
      setError('Unable to connect to API. Make sure the server is running.');
      setTracks([]);
      setFilteredTracks([]);
    } finally {
      setLoading(false);
    }
  };

  const getRecommendations = async (track: Track) => {
    setRecommendationsLoading(true);
    setRecommendations([]);
    try {
      // Use the correct similar tracks endpoint
      const response = await fetch(`${API_BASE_URL}/similar/by_track/${track.plex_rating_key}?n_results=10`);
      if (response.ok) {
        const data = await response.json();
        // Check if it's a list of results or a confirmation required response
        if (Array.isArray(data)) {
          setRecommendations(data);
        } else if (data.status === 'confirmation_required') {
          // Handle confirmation required case
          setError('This track needs to be processed first. Processing can be done from the settings.');
        }
      }
    } catch (err) {
      console.error('Failed to get recommendations:', err);
    } finally {
      setRecommendationsLoading(false);
    }
  };

  const handleTrackSelect = (track: Track) => {
    setSelectedTrack(track);
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
        
        {/* Search Input */}
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
                onClick={fetchTracks}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                Retry
              </button>
            </div>
          ) : filteredTracks.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">🎵</div>
              <p className="text-gray-500 dark:text-gray-400 mb-2">
                {searchQuery ? 'No tracks found matching your search' : 'No tracks in your library yet'}
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500">
                {!searchQuery && 'Scan your Plex library first'}
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
                  {!track.processed && (
                    <div className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
                      Not yet processed for search
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Recommendations */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Recommendations
          </h3>
          
          {!selectedTrack ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-2">👆</div>
              <p className="text-gray-500 dark:text-gray-400">
                Select a track to see recommendations
              </p>
            </div>
          ) : recommendationsLoading ? (
            <div className="space-y-3">
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