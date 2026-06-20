import React from 'react';
import { FileText, Plus } from 'lucide-react';

interface DashboardEmptyProps {
  onCreateReport: () => void;
}

export const DashboardEmpty: React.FC<DashboardEmptyProps> = ({ onCreateReport }) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="text-center max-w-md">
        <div className="mb-6 flex justify-center">
          <div className="w-32 h-32 bg-gradient-to-br from-brand-50 to-brand-100 rounded-full flex items-center justify-center">
            <FileText className="w-16 h-16 text-brand-300" />
          </div>
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Nenhum relatório encontrado
        </h2>

        <p className="text-gray-600 mb-8">
          Você ainda não criou nenhum relatório de obra. Comece criando seu primeiro diário agora!
        </p>

        <button
          onClick={onCreateReport}
          className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 hover:shadow-lg hover:-translate-y-0.5"
          aria-label="Criar novo relatório"
        >
          <Plus className="w-5 h-5" />
          <span>Novo Relatório</span>
        </button>
      </div>
    </div>
  );
};
