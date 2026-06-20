from fastapi import HTTPException
from uuid import UUID
from app.db.models import Defect, DefectAuditLog
from sqlalchemy.orm import Session
from services.defect_query import SORT_FIELDS

def list_defects(db: Session, limit: int, offset: int, status: str = None, category: str = None, sort_by: str = None):
    base_query = db.query(Defect)
    if status is not None:
        base_query = base_query.filter(Defect.status == status)
    if category is not None:
        base_query = base_query.filter(Defect.category == category)
    if sort_by is not None:
        descending = sort_by.startswith("-")
        field_name = sort_by[1:] if descending else sort_by
        if field_name not in SORT_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid sort field: {field_name}")
        column = SORT_FIELDS[field_name]
        order_by = column.desc()
        if not descending:
            order_by = column.asc()
        base_query = base_query.order_by(order_by)
    else:
        base_query = base_query.order_by(Defect.created_at.desc())
    total = base_query.count()
    items = base_query.offset(offset).limit(limit).all()
    return items, total

def create_defect(db: Session, defect_data: dict) -> Defect:
    new_defect = Defect(
        reported_by=defect_data['reported_by'],
        category=defect_data['category'],
        subcategory=defect_data.get('subcategory'),
        description=defect_data.get('description'),
        absn=defect_data['absn'],
        assigned_to=defect_data.get('assigned_to'),
        status=defect_data['status']
    )
    db.add(new_defect)
    db.commit()
    db.refresh(new_defect)
    return new_defect

def get_defect(db: Session, defect_id: UUID) -> Defect:
    return db.query(Defect).filter(Defect.id == defect_id).first()

def update_defect(db: Session, defect_id: UUID, update_data: dict, updated_by: str) -> Defect:
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        return None
    old_status = defect.status
    defect.updated_by = updated_by
    for key, value in update_data.items():
        if value is not None:
            setattr(defect, key, value)
    new_status = defect.status
    if 'status' in update_data and old_status != new_status:
        audit_log_entry = DefectAuditLog(
            defect_id=defect_id,
            changed_by=updated_by,
            old_status=old_status,
            new_status=new_status
        )
        db.add(audit_log_entry)
    
    db.commit()
    db.refresh(defect)
    return defect
