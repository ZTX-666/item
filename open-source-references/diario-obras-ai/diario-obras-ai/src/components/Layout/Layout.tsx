import React from 'react';

interface LayoutProps {
  children: React.ReactNode;
  className?: string;
}

export const Layout: React.FC<LayoutProps> = ({ children, className = '' }) => {
  return (
    <div className={`min-h-screen bg-gray-100 ${className}`}>
      <div className="flex min-h-screen">
        <aside className="w-64 bg-primary text-white flex-shrink-0 hidden md:block">
          {/* Sidebar content will be injected */}
        </aside>

        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
