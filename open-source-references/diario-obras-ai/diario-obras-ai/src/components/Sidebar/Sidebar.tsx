import React from 'react';

interface SidebarProps {
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ className = '' }) => {
  return (
    <aside className={`w-64 bg-primary text-white p-6 ${className}`}>
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-2">Diário de Obras</h1>
        <p className="text-sm text-primary-light">AI-Powered Construction Logs</p>
      </div>

      <nav className="space-y-2">
        <a href="#" className="block px-4 py-2 rounded-lg bg-primary-dark hover:bg-primary transition-colors">
          Novo Diário
        </a>
        <a href="#" className="block px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors">
          Histórico
        </a>
        <a href="#" className="block px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors">
          Projetos
        </a>
        <a href="#" className="block px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors">
          Configurações
        </a>
      </nav>

      <div className="mt-auto pt-8 border-t border-primary-light">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
            <span className="text-sm font-bold">L</span>
          </div>
          <div>
            <p className="text-sm font-medium">Lucas LLD</p>
            <p className="text-xs text-primary-light">Engenheiro</p>
          </div>
        </div>
      </div>
    </aside>
  );
};
