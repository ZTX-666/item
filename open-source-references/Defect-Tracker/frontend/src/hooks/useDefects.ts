import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { defectsApi } from '../api/defects';
import type { Defect, DefectCreate, DefectUpdate, DefectStatus } from '@/types/defect';

export function useDefects() {
  return useQuery<Defect[], Error>({
    queryKey: ['defects'],
    queryFn: () => defectsApi.list(), 
  });
}

export function useCreateDefect() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DefectCreate) => defectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['defects'] });
    },
  });
}

export function useUpdateDefect() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<DefectUpdate> }) => 
      defectsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['defects'] });
    },
  });
}

export function useTransitionDefectStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, newStatus }: { id: string; newStatus: DefectStatus }) => 
      defectsApi.transitionStatus(id, newStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['defects'] });
    },
  });
}
