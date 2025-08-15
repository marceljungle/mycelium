'use client';

import { useState, useRef } from 'react';
import SearchResults from './SearchResults';
import { API_BASE_URL } from '../config/api';

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

export default function SearchInterface() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [audioLoading, setAudioLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<'text' | 'audio'>('text');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleTextSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/search/text?q=${encodeURIComponent(query)}&n_results=10`);

      if (!response.ok) {
        throw new Error('Search failed. Make sure the Mycelium API is running.');
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setResults([]);
    } finally {
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
      formData.append('n_results', '10');

      const response = await fetch(`${API_BASE_URL}/api/search/audio`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Audio search failed. Please check the server logs for details.');
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      console.error('Audio search error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred during audio search');
      setResults([]);
    } finally {
      setAudioLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Check file type
      const validTypes = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/flac', 'audio/ogg'];
      if (!validTypes.some(type => file.type.includes(type.split('/')[1]))) {
        setError('Please select a valid audio file (MP3, WAV, FLAC, or OGG)');
        return;
      }
      
      // Check file size (50MB limit)
      if (file.size > 50 * 1024 * 1024) {
        setError('File size must be less than 50MB');
        return;
      }

      setAudioFile(file);
      setError(null);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && searchType === 'text') {
      handleTextSearch();
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
        <div className="flex space-x-1 bg-gray-100 dark:bg-gray-700 p-1 rounded-lg w-fit">
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
                placeholder="Describe the music you're looking for... (e.g., 'upbeat 80s synthpop', 'melancholic acoustic')"
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
              />
            </div>
            <button
              onClick={handleTextSearch}
              disabled={loading || !query.trim()}
              className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading ? (
                <div className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Searching...
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
            <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6">
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
                        Supports MP3, WAV, FLAC, OGG (max 50MB)
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
              disabled={audioLoading || !audioFile}
              className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {audioLoading ? (
                <div className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyzing Audio...
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

      <SearchResults results={results} loading={loading || audioLoading} />
    </div>
  );
}