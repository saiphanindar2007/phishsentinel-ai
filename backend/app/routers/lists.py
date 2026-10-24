"""
PhishSentinel AI — Allow/Deny list management (admin only)
--------------------------------------------------------------
Operators curate domains that must never be flagged (allow) or always be
blocked (deny). Every change is audited and applied immediately.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import get_db
from app.logging_config import request_id_var
from app.schemas import ListEntryCreate, ListEntryOut
from app.security import client_ip, rate_limit, require_admin_key
from app.services.runtime import list_service

router = APIRouter(prefix="/lists", tags=["lists"], dependencies=[Depends(rate_limit)])


def _out(e) -> ListEntryOut:
    return ListEntryOut(id=e.id, kind=e.kind, domain=e.domain, note=e.note, created_by=e.created_by,
                        created_at=e.created_at.isoformat() if e.created_at else None)


@router.get("", response_model=List[ListEntryOut])
def get_lists(db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    return [_out(e) for e in crud.list_entries(db)]


@router.post("", response_model=ListEntryOut, status_code=201)
def add_entry(req: ListEntryCreate, request: Request, db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    entry = crud.add_list_entry(db, req.kind, req.domain, req.note, actor)
    if entry is None:
        raise HTTPException(status_code=409, detail="That domain is already on this list")
    crud.add_audit(db, actor, "list_add", f"{req.kind}:{req.domain}", client_ip(request), request_id_var.get() or "")
    list_service.reload()
    return _out(entry)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, request: Request, db: Session = Depends(get_db), actor: str = Depends(require_admin_key)):
    entry = crud.delete_list_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    crud.add_audit(db, actor, "list_delete", f"{entry.kind}:{entry.domain}", client_ip(request), request_id_var.get() or "")
    list_service.reload()
