import { Report } from '../types';

export const mockReports: Report[] = [
  {
    id: '1',
    projectName: 'Obra Residencial Solaris',
    createdAt: new Date('2026-01-10'),
    photoCount: 24,
    thumbnailUrl: 'https://picsum.photos/seed/report1/400/300',
    downloadUrl: '/mock-downloads/obra-solaris.docx'
  },
  {
    id: '2',
    projectName: 'Reforma Apartamento Centro',
    createdAt: new Date('2026-01-08'),
    photoCount: 18,
    thumbnailUrl: 'https://picsum.photos/seed/report2/400/300',
    downloadUrl: '/mock-downloads/reforma-centro.docx'
  },
  {
    id: '3',
    projectName: 'Construção Shopping Via',
    createdAt: new Date('2025-12-28'),
    photoCount: 47,
    thumbnailUrl: 'https://picsum.photos/seed/report3/400/300',
    downloadUrl: '/mock-downloads/shopping-via.docx'
  },
  {
    id: '4',
    projectName: 'Piscina Clube Recreativo',
    createdAt: new Date('2025-12-22'),
    photoCount: 32,
    thumbnailUrl: 'https://picsum.photos/seed/report4/400/300',
    downloadUrl: '/mock-downloads/piscina-clube.docx'
  },
  {
    id: '5',
    projectName: 'Pavimentação Rua Principal',
    createdAt: new Date('2025-12-15'),
    photoCount: 15,
    thumbnailUrl: 'https://picsum.photos/seed/report5/400/300',
    downloadUrl: '/mock-downloads/pavimentacao-rua.docx'
  }
];
