'use client';

import { useState } from 'react';
import SearchInterface from '@/components/SearchInterface';
import LibraryStats from '@/components/LibraryStats';
import Header from '@/components/Header';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <Header />
      
      <main className="container mx-auto px-4 py-8">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
            🍄 Mycelium
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            Discover your music collection like never before. Using AI-powered embeddings 
            to find perfect matches based on sound, mood, and style.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Search Interface */}
          <div className="lg:col-span-2">
            <SearchInterface />
          </div>
          
          {/* Library Stats Sidebar */}
          <div className="lg:col-span-1">
            <LibraryStats />
          </div>
        </div>

        {/* Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">🎵</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Semantic Search
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Find music using natural language. Search for "upbeat indie rock" or "melancholic piano".
            </p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">🧠</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              AI-Powered
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Uses CLAP (Contrastive Language-Audio Pre-training) for understanding music content.
            </p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">📚</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Plex Integration
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Seamlessly connects with your existing Plex music library.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
