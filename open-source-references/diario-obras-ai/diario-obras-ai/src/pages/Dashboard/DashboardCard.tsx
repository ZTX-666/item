import React from 'react';
import { Report } from '../../types';
import { FileText, Download, Calendar, Image as ImageIcon } from 'lucide-react';

interface DashboardCardProps {
  report: Report;
  onDownload: (reportId: string) => void;
}

export const DashboardCard: React.FC<DashboardCardProps> = ({ report, onDownload }) => {
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    }).format(new Date(date));
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDownload(report.id);
  };

  return (
    <article
      className="group bg-white rounded-xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden cursor-pointer border border-gray-100"
      role="article"
      aria-label={`Relatório: ${report.projectName}`}
    >
      <div className="relative h-40 overflow-hidden bg-gradient-to-br from-brand-50 to-brand-100">
        {report.thumbnailUrl ? (
          <img
            src={report.thumbnailUrl}
            alt={`Thumbnail de ${report.projectName}`}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon className="w-16 h-16 text-brand-300 opacity-50" />
          </div>
        )}
        <div className="absolute top-3 right-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold ${
              report.status === 'complete'
                ? 'bg-brand-500 text-white'
                : 'bg-yellow-500 text-white'
            }`}
          >
            {report.status === 'complete' ? 'Completo' : 'Rascunho'}
          </span>
        </div>
      </div>

      <div className="p-5">
        <h3 className="text-lg font-bold text-gray-900 mb-2 line-clamp-1" title={report.projectName}>
          {report.projectName}
        </h3>

        <div className="space-y-2 mb-4">
          <div className="flex items-center text-sm text-gray-600">
            <Calendar className="w-4 h-4 mr-2 text-gray-400" />
            <span>{formatDate(report.createdAt)}</span>
          </div>
          <div className="flex items-center text-sm text-gray-600">
            <ImageIcon className="w-4 h-4 mr-2 text-gray-400" />
            <span>{report.photoCount} {report.photoCount === 1 ? 'foto' : 'fotos'}</span>
          </div>
          {report.projectLocation && (
            <div className="flex items-center text-sm text-gray-600">
              <FileText className="w-4 h-4 mr-2 text-gray-400" />
              <span className="line-clamp-1" title={report.projectLocation}>
                {report.projectLocation}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-gray-100">
          <span className="text-xs text-gray-500">
            {report.supervisor && `Resp: ${report.supervisor}`}
          </span>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
            aria-label={`Baixar DOCX de ${report.projectName}`}
          >
            <Download className="w-4 h-4" />
            <span>DOCX</span>
          </button>
        </div>
      </div>
    </article>
  );
};
