from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.domains.enums import DefectStatus

class DefectCreate(BaseModel):
    reported_by: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    absn: str
    assigned_to: Optional[str] = None
    status: DefectStatus

class DefectOut(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None
    reported_by: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    absn: str
    assigned_to: Optional[str] = None
    status: DefectStatus

    model_config = ConfigDict(from_attributes=True)

class DefectListOut(BaseModel):
    items: List[DefectOut]
    limit: int
    offset: int
    sort_by: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    total: int

    model_config = ConfigDict(from_attributes=True)

class DefectUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[DefectStatus] = None

class DefectAuditLogOut(BaseModel):
    id: UUID
    defect_id: UUID
    changed_at: datetime
    changed_by: str
    old_status: str
    new_status: str

    model_config = ConfigDict(from_attributes=True)
