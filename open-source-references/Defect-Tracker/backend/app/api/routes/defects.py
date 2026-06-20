from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import require_scopes, get_current_user
from app.db.models import Defect, DefectAuditLog, User
from app.db.session import get_db
from schemas.defects import DefectListOut, DefectCreate, DefectOut, DefectUpdate, DefectAuditLogOut
from sqlalchemy.orm import Session
from services.defects import list_defects, create_defect, get_defect, update_defect
from services.defect_query import SORT_FIELDS

router = APIRouter(prefix="/defects", tags=["defects"])

@router.get("", dependencies=[Depends(require_scopes(["quality:defects:read"]))], response_model=DefectListOut)
def get_defects(limit: int = 50, offset: int = 0, status: str = None, category: str = None, sort_by: str = None, db: Session = Depends(get_db)):
    items, total = list_defects(db, limit, offset, status=status, category=category, sort_by=sort_by)
    return DefectListOut(items=items, limit=limit, offset=offset, total=total, status=status, category=category)

@router.post("", response_model=DefectOut, status_code=201)
def create_new_defect(defect_data: DefectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_defect = create_defect(db, defect_data.model_dump())
    return new_defect

@router.get("/{defect_id}", response_model=DefectOut)
def get_defect_by_id(defect_id: UUID, db: Session = Depends(get_db)):
    defect = get_defect(db, defect_id)
    if not defect:
        raise HTTPException(status_code=404, detail="Defect not found")
    return defect

@router.patch("/{defect_id}", response_model=DefectOut)
def update_defect_by_id(defect_id: UUID, update_data: DefectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    updated_defect = update_defect(db, defect_id, update_data.model_dump(exclude_unset=True), updated_by=current_user.id)
    if not updated_defect:
        raise HTTPException(status_code=404, detail="Defect not found")
    return updated_defect
    
@router.get("/{defect_id}/audit", response_model=list[DefectAuditLogOut])
def get_defect_audit_log(defect_id: UUID, db: Session = Depends(get_db)):
    audit_log_entries = db.query(DefectAuditLog).filter(DefectAuditLog.defect_id == defect_id).order_by(DefectAuditLog.changed_at.desc()).all()
    if not audit_log_entries:
        raise HTTPException(status_code=404, detail="No audit log entries found for this defect")
    else:
        return audit_log_entries


