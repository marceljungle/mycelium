'use client';

import { useState } from 'react';
import PlaylistCreationModal from './PlaylistCreationModal';

interface SearchResult {
  track: {
    artist: string;
    album: string;
    title: string;
    filepath: string;
    plex_rating_key: string;
  };
  similarity_score: number;
  distance: number;
}

interface SearchResultsProps {
  results: SearchResult[];
  loading: boolean;
}

export default function SearchResults({ results, loading }: SearchResultsProps) {
  const [isPlaylistModalOpen, setIsPlaylistModalOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="animate-pulse">
            <div className="bg-gray-200 dark:bg-gray-700 h-20 rounded-lg"></div>
          </div>
        ))}
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">🎯</div>
        <p className="text-gray-500 dark:text-gray-400">
          Search for music using natural language descriptions
        </p>
        <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
          Try searching for moods, genres, instruments, or vibes
        </p>
      </div>
    );
  }

  const handlePlaylistCreated = (playlistName: string) => {
    setSuccessMessage(`Successfully created playlist "${playlistName}" with ${results.length} tracks!`);
    setTimeout(() => setSuccessMessage(null), 5000);
  };

  const trackIds = results.map(result => result.track.plex_rating_key);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Found {results.length} similar tracks
        </h3>
        
        {results.length > 0 && (
          <button
            onClick={() => setIsPlaylistModalOpen(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path>
            </svg>
            <span>Create Playlist</span>
          </button>
        )}
      </div>

      {successMessage && (
        <div className="mb-4 p-4 bg-green-100 dark:bg-green-900 border border-green-300 dark:border-green-700 rounded-lg">
          <p className="text-green-700 dark:text-green-300 flex items-center">
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
            {successMessage}
          </p>
        </div>
      )}
      
      {results.map((result, index) => (
        <div 
          key={result.track.plex_rating_key}
          className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <div className="text-lg font-medium text-purple-600 dark:text-purple-400">
                  #{index + 1}
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white">
                    {result.track.title}
                  </h4>
                  <p className="text-gray-600 dark:text-gray-300">
                    {result.track.artist} • {result.track.album}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="text-right">
              <div className="text-sm font-medium text-gray-900 dark:text-white">
                {Math.round(result.similarity_score * 100)}% match
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Distance: {result.distance.toFixed(3)}
              </div>
            </div>
          </div>
          
          {/* Progress bar for similarity */}
          <div className="mt-3">
            <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
              <div 
                className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.round(result.similarity_score * 100)}%` }}
              ></div>
            </div>
          </div>
          
          {/* File path (truncated) */}
          <div className="mt-2 text-xs text-gray-400 dark:text-gray-500 font-mono">
            {result.track.filepath.length > 60 
              ? '...' + result.track.filepath.slice(-60)
              : result.track.filepath
            }
          </div>
        </div>
      ))}
      
      <PlaylistCreationModal
        isOpen={isPlaylistModalOpen}
        onClose={() => setIsPlaylistModalOpen(false)}
        trackIds={trackIds}
        onSuccess={handlePlaylistCreated}
      />
    </div>
  );
}