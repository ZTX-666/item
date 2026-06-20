from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from services.safety_incidents import create_incident, update_incident, transition_status, get_incident
from app.db.models import User, SafetyIncidentAuditLog
from app.core.auth import get_current_user, require_scopes
from schemas.safety import SafetyIncidentCreate, SafetyIncidentAuditLogOut, SafetyIncidentUpdate, SafetyIncidentOut, SafetyIncidentStatusUpdate
from uuid import UUID

router = APIRouter(prefix="/safety/incidents", tags=["Safety"])

@router.post("", dependencies=[Depends(require_scopes(["safety:incidents:write"]))], response_model=SafetyIncidentOut, status_code=201)
def create_safety_incident(payload: SafetyIncidentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        incident = create_incident(db, payload.model_dump(), current_user)
        return incident
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.patch("/{incident_id}", dependencies=[Depends(require_scopes(["safety:incidents:write"]))], response_model=SafetyIncidentOut)
def update_incident_by_id(incident_id: UUID, payload: SafetyIncidentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        updated = update_incident(db, incident_id, payload.model_dump(exclude_unset=True), current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    return updated

@router.patch("/{incident_id}/status", dependencies=[Depends(require_scopes(["safety:incidents:write"]))], response_model=SafetyIncidentOut)
def update_incident_status(incident_id: UUID, payload: SafetyIncidentStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        updated = transition_status(db, incident_id, payload.status, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    return updated

@router.get("/{incident_id}", dependencies=[Depends(require_scopes(["safety:incidents:read"]))],response_model=SafetyIncidentOut)
def get_incident_by_id(incident_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
    
@router.get("/{incident_id}/audit", dependencies=[Depends(require_scopes(["safety:incidents:read"]))], response_model=list[SafetyIncidentAuditLogOut])
def get_safety_incident_audit_log(incident_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = (db.query(SafetyIncidentAuditLog).filter(SafetyIncidentAuditLog.incident_id == incident_id).order_by(SafetyIncidentAuditLog.changed_at.desc()).all())
    return entries
    
