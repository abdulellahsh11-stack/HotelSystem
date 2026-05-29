#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M07 — الإشراف الداخلي Housekeeping"""
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/m07", tags=["Housekeeping"])


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/tasks")
async def list_tasks(request: Request, status: Optional[str] = None,
                     session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        q = """SELECT t.*, r.room_number
               FROM housekeeping_tasks t LEFT JOIN rooms r ON t.room_id = r.id
               WHERE t.client_id = %s"""
        params = [cid]
        if status: q += " AND t.status = %s"; params.append(status)
        q += " ORDER BY t.created_at DESC LIMIT 100"
        rows = db.execute(q, params, fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/tasks")
async def create_task(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute("""
            INSERT INTO housekeeping_tasks
                (client_id,room_id,task_type,priority,assigned_to,status,notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (cid, data.get("room_id"), data.get("task_type", "cleaning"),
              data.get("priority", "normal"), data.get("assigned_to"),
              "pending", data.get("notes")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}


@router.put("/tasks/{task_id}/status")
async def update_task_status(task_id: int, request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    new_status = data.get("status", "completed")
    if db.use_postgres:
        extra = ""
        if new_status == "in_progress":
            extra = ", started_at = NOW()"
        elif new_status == "completed":
            extra = ", completed_at = NOW()"
        db.execute(
            f"UPDATE housekeeping_tasks SET status=%s{extra} WHERE id=%s AND client_id=%s",
            (new_status, task_id, cid))
    return {"success": True}


@router.get("/rooms/status")
async def rooms_status(request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        rows = db.execute(
            "SELECT room_number, status, floor, room_type FROM rooms WHERE client_id=%s ORDER BY room_number",
            (cid,), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/rooms/{room_number}/clean")
async def mark_room_clean(room_number: str, request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        db.execute(
            "UPDATE rooms SET status='clean' WHERE room_number=%s AND client_id=%s",
            (room_number, cid))
        db.execute("""
            INSERT INTO housekeeping_tasks (client_id,task_type,status,notes)
            SELECT %s,'cleaning','completed','تنظيف غرفة '||room_number
            FROM rooms WHERE room_number=%s AND client_id=%s
        """, (cid, room_number, cid))
    return {"success": True}


@router.get("/lost-found")
async def list_lost_found(request: Request, session=Depends(_require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        rows = db.execute(
            "SELECT * FROM lost_and_found WHERE client_id=%s ORDER BY created_at DESC",
            (cid,), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/lost-found")
async def add_lost_found(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    if db.use_postgres:
        row = db.execute("""
            INSERT INTO lost_and_found
                (client_id,room_id,item_description,found_date,found_by,status,notes)
            VALUES (%s,%s,%s,%s,%s,'stored',%s) RETURNING *
        """, (cid, data.get("room_id"), data.get("item_description", ""),
              data.get("found_date"), data.get("found_by"),
              data.get("notes")), fetch="one")
        return {"success": True, "data": dict(row)}
    return {"success": True, "data": data}
