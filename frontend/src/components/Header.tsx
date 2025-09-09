'use client';

import Navigation, { Section } from './Navigation';
import { useProcessing } from '../contexts/ProcessingContext';

interface HeaderProps {
  activeSection: Section;
  onSectionChange: (section: Section) => void;
}

export default function Header({ activeSection, onSectionChange }: HeaderProps) {
  const { processLoading, progressInfo, stopProcessing } = useProcessing();

  return (
    <header className="bg-white dark:bg-gray-800 shadow-sm">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🍄</span>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">
              Mycelium
            </h1>
          </div>
          
          <Navigation activeSection={activeSection} onSectionChange={onSectionChange} />
          
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
          </div>
        </div>
      </div>
    </header>
  );
}