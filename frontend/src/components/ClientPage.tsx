'use client';

import ClientSettingsPage from '@/components/ClientSettingsPage';
import { useProcessing } from '@/contexts/ProcessingContext';
import { ProcessingProvider } from '@/contexts/ProcessingContext';

function ClientPageContent() {
  const { processLoading, progressInfo, stopProcessing } = useProcessing();

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
            
            <div className="flex items-center space-x-2">
              {/* Processing Status Indicator */}
              {processLoading && (
                <div className="flex items-center space-x-2 px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-sm font-medium">
                    {progressInfo?.stage === 'processing' && progressInfo.current && progressInfo.total
                      ? `Processing ${progressInfo.current}/${progressInfo.total}`
                      : 'Processing...'
                    }
                  </span>
                  <button
                    onClick={stopProcessing}
                    className="ml-2 px-2 py-1 text-xs bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-800"
                    title="Stop Processing"
                  >
                    🛑
                  </button>
                </div>
              )}
              
              <button className="p-2 text-gray-600 dark:text-gray-300 hover:text-purple-600 dark:hover:text-purple-400 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              </button>
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

export default function ClientPage() {
  return (
    <ProcessingProvider>
      <ClientPageContent />
    </ProcessingProvider>
  );
}