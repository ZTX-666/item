import React, { useState, useMemo, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { DashboardCard } from './DashboardCard';
import { DashboardFilter, DashboardFilters } from './DashboardFilter';
import { DashboardEmpty } from './DashboardEmpty';
import { storageService } from '../../services/storageService';

const ITEMS_PER_PAGE = 10;

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState(storageService.getAllReports());
  const [filters, setFilters] = useState<DashboardFilters>({
    projectSearch: ''
  });
  const [currentPage, setCurrentPage] = useState(1);

  // Atualizar lista quando houver mudanças no localStorage
  useEffect(() => {
    const handleStorageChange = () => {
      setReports(storageService.getAllReports());
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const filteredReports = useMemo(() => {
    return reports
      .filter(report => {
        if (filters.projectSearch.trim() !== '') {
          const searchLower = filters.projectSearch.toLowerCase();
          const projectNameMatch = report.projectName.toLowerCase().includes(searchLower);
          const locationMatch = report.projectLocation?.toLowerCase().includes(searchLower);
          const contractorMatch = report.contractor?.toLowerCase().includes(searchLower);
          
          if (!projectNameMatch && !locationMatch && !contractorMatch) {
            return false;
          }
        }

        if (filters.dateFrom && new Date(report.createdAt) < filters.dateFrom) {
          return false;
        }

        if (filters.dateTo && new Date(report.createdAt) > filters.dateTo) {
          return false;
        }

        return true;
      })
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [filters]);

  const totalPages = Math.ceil(filteredReports.length / ITEMS_PER_PAGE);
  const paginatedReports = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    return filteredReports.slice(start, end);
  }, [filteredReports, currentPage]);

  const handleFiltersChange = (newFilters: DashboardFilters) => {
    setFilters(newFilters);
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setFilters({ projectSearch: '' });
    setCurrentPage(1);
  };

  const handleDownload = (reportId: string) => {
    alert(`Download DOCX for report ${reportId} (mock)`);
  };

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleCreateReport = () => {
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="flex min-h-screen">
        <aside className="w-64 bg-primary text-white p-6 hidden md:block">
          <div className="mb-8">
            <h1 className="text-2xl font-bold mb-2">Diário de Obras</h1>
            <p className="text-sm text-primary-light">AI-Powered Construction Logs</p>
          </div>

          <nav className="space-y-2">
            <Link
              to="/"
              className="block px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors"
            >
              Novo Diário
            </Link>
            <Link
              to="/dashboard"
              className="block px-4 py-2 rounded-lg bg-primary-dark hover:bg-primary transition-colors"
            >
              Histórico
            </Link>
          </nav>
        </aside>

        <main className="flex-1 overflow-auto">
          <div className="container mx-auto px-6 py-8">
            <header className="mb-8">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-bold text-primary-dark mb-2">
                    Histórico de Relatórios
                  </h1>
                  <p className="text-primary">
                    Visualize e gerencie todos os seus relatórios de obra
                  </p>
                </div>

                <button
                  onClick={handleCreateReport}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-lg font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 hover:shadow-lg hover:-translate-y-0.5 self-start md:self-auto"
                  aria-label="Criar novo relatório"
                >
                  <Plus className="w-5 h-5" />
                  <span>Novo Relatório</span>
                </button>
              </div>

              <div className="mt-4 text-sm text-gray-600">
                {filteredReports.length} {filteredReports.length === 1 ? 'relatório encontrado' : 'relatórios encontrados'}
              </div>
            </header>

            <DashboardFilter
              filters={filters}
              onFiltersChange={handleFiltersChange}
              onClearFilters={handleClearFilters}
            />

            {filteredReports.length === 0 ? (
              <DashboardEmpty onCreateReport={handleCreateReport} />
            ) : (
              <>
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 mb-8">
                  {paginatedReports.map(report => (
                    <DashboardCard
                      key={report.id}
                      report={report}
                      onDownload={handleDownload}
                    />
                  ))}
                </div>

                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2">
                    <button
                      onClick={() => goToPage(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      aria-label="Página anterior"
                    >
                      Anterior
                    </button>

                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                      <button
                        key={page}
                        onClick={() => goToPage(page)}
                        className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                          currentPage === page
                            ? 'border-brand-600 bg-brand-600 text-white'
                            : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                        }`}
                        aria-label={`Ir para página ${page}`}
                        aria-current={currentPage === page ? 'page' : undefined}
                      >
                        {page}
                      </button>
                    ))}

                    <button
                      onClick={() => goToPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      aria-label="Próxima página"
                    >
                      Próxima
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
