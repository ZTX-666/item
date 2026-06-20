from uuid import UUID
from app.db.models import SafetyIncident, SafetyIncidentAuditLog, User
from sqlalchemy.orm import Session
from app.domains.enums import IncidentStatus, IncidentSeverity

ALLOWED_TRANSITIONS = {
        IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING},
        IncidentStatus.INVESTIGATING: {IncidentStatus.CORRECTIVE_ACTION},
        IncidentStatus.CORRECTIVE_ACTION: {IncidentStatus.CLOSED},
        IncidentStatus.CLOSED: set()
    }

def create_incident(db: Session, payload: dict, current_user: User) -> SafetyIncident:
    new_incident = SafetyIncident(
        reported_by=current_user.id,
        severity=payload['severity'],
        description=payload.get('description'),
        location=payload['location'],
        department=payload['department'],
        shift=payload['shift'],
        status=IncidentStatus.OPEN
    )
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)
    return new_incident

def update_incident(db: Session, incident_id: UUID, update_data: dict, current_user: User) -> SafetyIncident:
    incident = db.query(SafetyIncident).filter(SafetyIncident.id == incident_id).first()
    if not incident:
        return None
    
    if "status" in update_data:
        raise ValueError("Use transition_status to change status")
    
    for key, value in update_data.items():
        if value is None:
            continue
        if not hasattr(incident, key):
            raise ValueError(f"Unknown field: {key}")
        setattr(incident, key, value)

    db.commit()
    db.refresh(incident)
    return incident

def transition_status(db: Session, incident_id: UUID, new_status: IncidentStatus, current_user: User) -> SafetyIncident:
    incident = (db.query(SafetyIncident).filter(SafetyIncident.id == incident_id).first())
    if not incident:
        return None
    # no-op: don't audit/commit if nothing changes
    if new_status == incident.status:
        return incident
    allowed = ALLOWED_TRANSITIONS.get(incident.status, set())
    if new_status not in allowed:
        raise ValueError("Invalid status transition")
    # business rule: cannot close without corrective action
    if new_status == IncidentStatus.CLOSED:
        corrective = (incident.corrective_action or "").strip()
        if not corrective:
            raise ValueError("Cannot close incident without corrective action")
    old_status = incident.status
    incident.status = new_status
    audit_log_entry = SafetyIncidentAuditLog(
        incident_id=incident.id,
        changed_by=current_user.id,
        old_status=old_status,
        new_status=new_status,
    )
    db.add(audit_log_entry)

    db.commit()
    db.refresh(incident)
    return incident

def list_incidents(db: Session, limit: int, offset: int, status: IncidentStatus = None, severity: IncidentSeverity = None) -> tuple[list[SafetyIncident], int]:
    base_query = db.query(SafetyIncident)
    if status is not None:
        base_query = base_query.filter(SafetyIncident.status == status)
    if severity is not None:
        base_query = base_query.filter(SafetyIncident.severity == severity)
    total = base_query.count()
    items = base_query.order_by(SafetyIncident.created_at.desc()).offset(offset).limit(limit).all()
    return items, total

def get_incident(db: Session, incident_id: UUID) -> SafetyIncident | None:
    return (db.query(SafetyIncident).filter(SafetyIncident.id == incident_id).first())

