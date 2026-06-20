export type IncidentStatus = "open" | "investigating" | "corrective_action" | "closed"; 
export type IncidentSeverity = "near_miss" | "soreness" | "first_aid" | "recordable" | "psif";

export interface SafetyIncidentCreate {
    severity: IncidentSeverity;
    description?: string;
    location: string;
    department: string;
    shift: string;
}

export interface SafetyIncidentUpdate {
    severity?: IncidentSeverity;
    description?: string;
    location?: string;
    department?: string;
    shift?: string;
    corrective_action?: string;
}

export interface SafetyIncidentOut {
    id: string;
    severity: IncidentSeverity;
    description?: string;
    location: string;
    department: string;
    shift: string;
    status: IncidentStatus;
    corrective_action?: string;
    reported_by: string;
    created_at: string;
}

export interface SafetyIncidentAuditLog {
    id: string;
    incident_id: string;
    changed_by: string;
    old_status: IncidentStatus;
    new_status: IncidentStatus;
    changed_at: string;
}

export interface SafetyIncidentStatusUpdate {
    status: IncidentStatus;
}

