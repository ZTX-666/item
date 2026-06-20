import React from 'react';
import { Search, Calendar, X } from 'lucide-react';

export interface DashboardFilters {
  dateFrom?: Date;
  dateTo?: Date;
  projectSearch: string;
}

interface DashboardFilterProps {
  filters: DashboardFilters;
  onFiltersChange: (filters: DashboardFilters) => void;
  onClearFilters: () => void;
}

export const DashboardFilter: React.FC<DashboardFilterProps> = ({
  filters,
  onFiltersChange,
  onClearFilters
}) => {
  const hasActiveFilters =
    filters.dateFrom ||
    filters.dateTo ||
    filters.projectSearch.trim() !== '';

  const handleProjectSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({
      ...filters,
      projectSearch: e.target.value
    });
  };

  const handleDateFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({
      ...filters,
      dateFrom: e.target.value ? new Date(e.target.value) : undefined
    });
  };

  const handleDateToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({
      ...filters,
      dateTo: e.target.value ? new Date(e.target.value) : undefined
    });
  };

  const formatDateForInput = (date?: Date) => {
    if (!date) return '';
    return new Date(date).toISOString().split('T')[0];
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-6 mb-6">
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Filtrar Relatórios</h2>
        {hasActiveFilters && (
          <button
            onClick={onClearFilters}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 rounded-lg"
            aria-label="Limpar filtros"
          >
            <X className="w-4 h-4" />
            <span>Limpar Filtros</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="project-search" className="block text-sm font-medium text-gray-700 mb-2">
            Buscar Projeto
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              id="project-search"
              type="text"
              value={filters.projectSearch}
              onChange={handleProjectSearchChange}
              placeholder="Nome do projeto..."
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
              aria-label="Buscar por nome do projeto"
            />
          </div>
        </div>

        <div>
          <label htmlFor="date-from" className="block text-sm font-medium text-gray-700 mb-2">
            Data Inicial
          </label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              id="date-from"
              type="date"
              value={formatDateForInput(filters.dateFrom)}
              onChange={handleDateFromChange}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
              aria-label="Data inicial"
            />
          </div>
        </div>

        <div>
          <label htmlFor="date-to" className="block text-sm font-medium text-gray-700 mb-2">
            Data Final
          </label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              id="date-to"
              type="date"
              value={formatDateForInput(filters.dateTo)}
              onChange={handleDateToChange}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
              aria-label="Data final"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
