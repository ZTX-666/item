export type DefectStatus = "open" | "repaired";

export interface DefectCreate {
  reported_by: string;
  category: string;
  subcategory?: string;
  description?: string;
  absn: string;
  assigned_to?: string;
  status: DefectStatus;
}

export interface DefectUpdate {
  category?: string;
  subcategory?: string;
  description?: string;
  assigned_to?: string;
  status?: DefectStatus;
}

export interface Defect extends DefectCreate {
  id: string;
  created_at: string;
  updated_at: string;
  updated_by?: string;
}
