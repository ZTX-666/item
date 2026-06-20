import { apiClient } from './client';
import type { Defect, DefectCreate, DefectUpdate, DefectStatus } from '@/types/defect';

export const defectsApi = {
  list: () => 
    apiClient.get<Defect[]>('/defects'),
  
  get: (id: string) => 
    apiClient.get<Defect>(`/defects/${id}`),
  
  create: (data: DefectCreate) => 
    apiClient.post<Defect>('/defects', data),
  
  update: (id: string, data: Partial<DefectUpdate>) => 
    apiClient.patch<Defect>(`/defects/${id}`, data),
  
  transitionStatus: (id: string, newStatus: DefectStatus) => 
    apiClient.patch<Defect>(`/defects/${id}`, { status: newStatus }),
};