import { apiClient } from './client';
import type { SafetyIncidentCreate, SafetyIncidentOut, SafetyIncidentUpdate, 
    SafetyIncidentAuditLog, IncidentStatus } from '@/types/safety';

export const safetyApi = {
  create: (data: SafetyIncidentCreate) => 
    apiClient.post<SafetyIncidentOut>('/safety/incidents', data),
  
  get: (id: string) => 
    apiClient.get<SafetyIncidentOut>(`/safety/incidents/${id}`),
  
  update: (id: string, data: Partial<SafetyIncidentUpdate>) => 
    apiClient.patch<SafetyIncidentOut>(`/safety/incidents/${id}`, data),
  
  transitionStatus: (id: string, newStatus: IncidentStatus) => 
    apiClient.patch<SafetyIncidentOut>(`/safety/incidents/${id}/status`, { status: newStatus }),
  
  getAuditLog: (id: string) => 
    apiClient.get<SafetyIncidentAuditLog[]>(`/safety/incidents/${id}/audit`),
};