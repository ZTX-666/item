from app.db.models import Defect

SORT_FIELDS = {
    "reported_by": Defect.reported_by,
    "absn": Defect.absn,
    "created_at": Defect.created_at,
    "updated_at": Defect.updated_at,
    "category": Defect.category,
    "subcategory": Defect.subcategory,
    "status": Defect.status,
}