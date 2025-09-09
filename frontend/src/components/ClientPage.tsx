'use client';

import ClientSettingsPage from '@/components/ClientSettingsPage';

export default function ClientPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      {/* Client-specific header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">🍄</span>
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                Mycelium Client
              </h1>
            </div>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-4">
            🍄 Mycelium Client
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            GPU worker configuration for distributed audio processing. Configure your client settings to connect to the Mycelium server.
          </p>
        </div>

        <div className="grid gap-8 grid-cols-1">
          <ClientSettingsPage />
        </div>

        {/* Client Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">🖥️</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              GPU Worker
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Dedicated worker for processing CLAP embeddings with GPU acceleration.
            </p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">🧠</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              AI Model Configuration
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Choose and configure the CLAP model for your specific use case.
            </p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <div className="text-2xl mb-3">🔗</div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Server Connection
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              Connect to your Mycelium server for distributed processing.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}