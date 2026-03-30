'use client';

type Section = 'search' | 'library' | 'queue' | 'settings';

interface NavigationProps {
  activeSection: Section;
  onSectionChange: (section: Section) => void;
}

export default function Navigation({ activeSection, onSectionChange }: NavigationProps) {
  const sections = [
    { id: 'search' as Section, name: 'Search', icon: '🔍' },
    { id: 'library' as Section, name: 'Library', icon: '📚' },
    { id: 'queue' as Section, name: 'Queue', icon: '📋' },
    { id: 'settings' as Section, name: 'Settings', icon: '⚙️' },
  ];

  return (
    <nav className="hidden md:flex items-center space-x-6">
      {sections.map((section) => (
        <button
          key={section.id}
          onClick={() => onSectionChange(section.id)}
          className={`
            flex items-center space-x-2 px-3 py-2 rounded-lg font-medium transition-colors
            ${activeSection === section.id
              ? 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/30'
              : 'text-gray-600 dark:text-gray-300 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-gray-50 dark:hover:bg-gray-700'
            }
          `}
        >
          <span className="text-lg">{section.icon}</span>
          <span>{section.name}</span>
        </button>
      ))}
    </nav>
  );
}

export type { Section };