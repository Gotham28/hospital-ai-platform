from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_db, get_current_tenant
from app.models.usage import UsageLedger # Import from the model file

router = APIRouter(tags=["Usage"])

@router.get("/summary")
def get_usage_summary(
    db: Session = Depends(get_db),
    hospital_id: int = Depends(get_current_tenant) # The Magic Key
):
    stats = db.query(
        func.sum(UsageLedger.total_tokens).label("total_tokens"),
        func.sum(UsageLedger.estimated_cost).label("estimated_cost")
    ).filter(UsageLedger.hospital_id == hospital_id).first()

    return {
        "total_tokens": stats.total_tokens or 0,
        "estimated_cost": stats.estimated_cost or 0.0
    }