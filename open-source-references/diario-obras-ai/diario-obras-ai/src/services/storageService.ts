import { Report } from '../types';

const STORAGE_KEY = 'diario_obras_reports';

export const storageService = {
  /**
   * Salva um relatório no localStorage
   */
  saveReport(report: Report): void {
    const reports = this.getAllReports();
    reports.push(report);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
  },

  /**
   * Retorna todos os relatórios salvos
   */
  getAllReports(): Report[] {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];

    try {
      const reports = JSON.parse(stored);
      // Converter strings de data para Date objects
      return reports.map((r: any) => ({
        ...r,
        createdAt: new Date(r.createdAt)
      }));
    } catch (error) {
      console.error('Erro ao carregar relatórios:', error);
      return [];
    }
  },

  /**
   * Retorna um relatório específico por ID
   */
  getReportById(id: string): Report | null {
    const reports = this.getAllReports();
    return reports.find(r => r.id === id) || null;
  },

  /**
   * Deleta um relatório
   */
  deleteReport(id: string): void {
    const reports = this.getAllReports();
    const filtered = reports.filter(r => r.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
  },

  /**
   * Limpa todos os relatórios (útil para debug)
   */
  clearAll(): void {
    localStorage.removeItem(STORAGE_KEY);
  },

  /**
   * Atualiza um relatório existente
   */
  updateReport(id: string, updates: Partial<Report>): void {
    const reports = this.getAllReports();
    const index = reports.findIndex(r => r.id === id);

    if (index !== -1) {
      reports[index] = { ...reports[index], ...updates };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
    }
  }
};
