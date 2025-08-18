'use client';

import Navigation, { Section } from './Navigation';

interface HeaderProps {
  activeSection: Section;
  onSectionChange: (section: Section) => void;
}

export default function Header({ activeSection, onSectionChange }: HeaderProps) {
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
            <button className="p-2 text-gray-600 dark:text-gray-300 hover:text-purple-600 dark:hover:text-purple-400 rounded-lg">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}