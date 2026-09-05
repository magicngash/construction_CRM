from datetime import date, datetime, timedelta, timezone
import json
import os
import urllib.error
import urllib.request
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware

from database import supabase
import schemas as s

app = FastAPI(title="Contractor Site Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this once you know your Streamlit deployment origin
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_date_fields(payload: dict) -> dict:
    """Convert date objects to ISO strings for the Supabase client."""
    out = {}
    for k, v in payload.items():
        out[k] = v.isoformat() if isinstance(v, date) else v
    return out


def _run(query):
    res = query.execute()
    return res.data


# =============================================================================
# PROJECTS
# =============================================================================
@app.get("/projects", response_model=List[s.ProjectOut])
def list_projects():
    return _run(supabase.table("sitemgr_projects").select("*").order("created_at", desc=True))


@app.post("/projects", response_model=s.ProjectOut)
def create_project(payload: s.ProjectCreate):
    data = _run(supabase.table("sitemgr_projects").insert(payload.model_dump()))
    return data[0]


@app.get("/projects/{project_id}", response_model=s.ProjectOut)
def get_project(project_id: str):
    data = _run(supabase.table("sitemgr_projects").select("*").eq("id", project_id))
    if not data:
        raise HTTPException(404, "Project not found")
    return data[0]


@app.patch("/projects/{project_id}", response_model=s.ProjectOut)
def update_project(project_id: str, payload: s.ProjectCreate):
    data = _run(
        supabase.table("sitemgr_projects").update(payload.model_dump()).eq("id", project_id)
    )
    if not data:
        raise HTTPException(404, "Project not found")
    return data[0]


@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    _run(supabase.table("sitemgr_projects").delete().eq("id", project_id))
    return {"deleted": True}


# =============================================================================
# TRANSACTIONS
# =============================================================================
@app.get("/transactions", response_model=List[s.TransactionOut])
def list_transactions(project_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_transactions").select("*").order("txn_date", desc=True)
    if project_id:
        q = q.eq("project_id", project_id)
    return _run(q)


@app.post("/transactions", response_model=s.TransactionOut)
def create_transaction(payload: s.TransactionCreate):
    body = _serialize_date_fields(payload.model_dump())
    data = _run(supabase.table("sitemgr_transactions").insert(body))
    return data[0]


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str):
    _run(supabase.table("sitemgr_transactions").delete().eq("id", transaction_id))
    return {"deleted": True}


# =============================================================================
# MATERIALS
# =============================================================================
@app.get("/materials", response_model=List[s.MaterialOut])
def list_materials(project_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_materials").select("*").order("item")
    if project_id:
        q = q.eq("project_id", project_id)
    return _run(q)


@app.post("/materials", response_model=s.MaterialOut)
def create_material(payload: s.MaterialCreate):
    if payload.in_stock < 0:
        raise HTTPException(400, "in_stock cannot be negative")
    if payload.in_stock > 0 and not (payload.opening_stock_recorded_by or "").strip():
        raise HTTPException(400, "opening stock must include the recording person's name")
    if payload.in_stock > 0 and (payload.opening_stock_unit_cost or 0) <= 0:
        raise HTTPException(400, "opening stock must include a unit cost")

    body = payload.model_dump(
        exclude={"opening_stock_recorded_by", "opening_stock_unit_cost"}
    )
    data = _run(supabase.table("sitemgr_materials").insert(body))
    material = data[0]

    if payload.in_stock > 0:
        _run(
            supabase.table("sitemgr_material_movements").insert(
                {
                    "material_id": material["id"],
                    "movement_type": "received",
                    "quantity": payload.in_stock,
                    "unit_cost": payload.opening_stock_unit_cost,
                    "recorded_by": payload.opening_stock_recorded_by.strip(),
                    "notes": "Opening stock",
                }
            )
        )

    return material


@app.post("/materials/{material_id}/movements", response_model=s.MaterialMovementOut)
def record_material_movement(material_id: str, payload: s.MaterialMovementCreate):
    if payload.material_id != material_id:
        raise HTTPException(400, "material_id mismatch")
    if payload.movement_type not in ("received", "used"):
        raise HTTPException(400, "movement_type must be 'received' or 'used'")
    if payload.quantity <= 0:
        raise HTTPException(400, "quantity must be greater than zero")
    if not (payload.recorded_by or "").strip():
        raise HTTPException(400, "recorded_by is required")
    if payload.movement_type == "received" and payload.unit_cost <= 0:
        raise HTTPException(400, "received stock must include a unit cost")
    if payload.movement_type == "received":
        if not (payload.receiver_name or payload.recorded_by or "").strip():
            raise HTTPException(400, "receiver_name is required for deliveries")
        if not (payload.checker_name or "").strip():
            raise HTTPException(400, "checker_name is required for deliveries")
        if payload.condition not in ("Good", "Damaged"):
            raise HTTPException(400, "condition must be Good or Damaged")
    else:
        if not (payload.recipient_name or "").strip() or not (payload.work_area or "").strip():
            raise HTTPException(400, "recipient_name and work_area are required for issuances")

    mat = _run(supabase.table("sitemgr_materials").select("*").eq("id", material_id))
    if not mat:
        raise HTTPException(404, "Material not found")
    current_stock = mat[0]["in_stock"]

    movement_history = _run(
        supabase.table("sitemgr_material_movements")
        .select("movement_type, quantity, unit_cost")
        .eq("material_id", material_id)
        .order("moved_at")
    ) or []
    inventory_value = 0.0
    running_stock = 0.0
    for movement in movement_history:
        movement_quantity = float(movement.get("quantity") or 0)
        movement_cost = float(movement.get("unit_cost") or 0)
        if movement.get("movement_type") == "received":
            inventory_value += movement_quantity * movement_cost
            running_stock += movement_quantity
        elif movement.get("movement_type") == "used":
            if running_stock <= 0:
                continue
            issue_cost = inventory_value / running_stock
            inventory_value -= movement_quantity * issue_cost
            running_stock -= movement_quantity

    current_stock = float(current_stock or 0)
    average_cost = inventory_value / running_stock if running_stock > 0 else 0
    unit_cost = payload.unit_cost if payload.movement_type == "received" else average_cost
    if payload.movement_type == "used" and current_stock > 0 and average_cost <= 0:
        raise HTTPException(
            400,
            "This stock has no recorded cost yet. Add an opening cost or receive stock with a unit cost first.",
        )

    delta = payload.quantity if payload.movement_type == "received" else -payload.quantity
    new_stock = current_stock + delta
    if new_stock < 0:
        raise HTTPException(400, "Resulting stock would be negative")

    movement_body = payload.model_dump()
    movement_body["unit_cost"] = unit_cost
    movement_body["recorded_by"] = payload.recorded_by.strip()
    data = _run(
        supabase.table("sitemgr_material_movements").insert(movement_body)
    )
    movement = data[0]
    _run(
        supabase.table("sitemgr_materials")
        .update({"in_stock": new_stock})
        .eq("id", material_id)
    )

    if payload.movement_type == "received":
        _run(
            supabase.table("sitemgr_transactions").insert(
                {
                    "project_id": mat[0]["project_id"],
                    "txn_date": date.today().isoformat(),
                    "category": "Materials",
                    "amount": payload.quantity * unit_cost,
                    "payee": payload.supplier,
                    "notes": payload.reference or payload.notes or "Stock receipt",
                    "source_movement_id": movement["id"],
                }
            )
        )

    return movement


@app.get("/materials/{material_id}/movements", response_model=List[s.MaterialMovementOut])
def list_material_movements(material_id: str):
    return _run(
        supabase.table("sitemgr_material_movements")
        .select("*")
        .eq("material_id", material_id)
        .order("moved_at", desc=True)
    )


@app.get("/materials/{material_id}/audit-book-balance")
def material_book_balance(material_id: str, audit_date: Optional[date] = Query(None)):
    q = supabase.table("sitemgr_material_movements").select("movement_type, quantity").eq("material_id", material_id)
    if audit_date:
        q = q.lte("event_date", audit_date.isoformat())
    movements = _run(q) or []
    balance = sum(float(row.get("quantity") or 0) * (1 if row.get("movement_type") == "received" else -1) for row in movements)
    return {"material_id": material_id, "audit_date": audit_date, "book_balance": balance}


@app.post("/materials/{material_id}/audits", response_model=s.StockAuditOut)
def create_stock_audit(material_id: str, payload: s.StockAuditCreate):
    if payload.material_id != material_id:
        raise HTTPException(400, "material_id mismatch")
    if payload.physical_count < 0 or not payload.counter_name.strip() or not payload.witness_name.strip():
        raise HTTPException(400, "physical count, counter, and witness are required")
    material = _run(supabase.table("sitemgr_materials").select("project_id").eq("id", material_id)) or []
    if not material:
        raise HTTPException(404, "Material not found")
    balance = material_book_balance(material_id, payload.audit_date)["book_balance"]
    variance = payload.physical_count - balance
    body = payload.model_dump()
    body.update({"book_balance": balance, "variance_quantity": variance, "variance_flag": abs(variance) > 0.0001})
    data = _run(supabase.table("sitemgr_material_audits").insert(_serialize_date_fields(body)))
    return data[0]


@app.get("/materials/{material_id}/audits", response_model=List[s.StockAuditOut])
def list_stock_audits(material_id: str):
    return _run(supabase.table("sitemgr_material_audits").select("*").eq("material_id", material_id).order("audit_date", desc=True)) or []


@app.post("/discrepancies", response_model=s.DiscrepancyOut)
def create_discrepancy(payload: s.DiscrepancyCreate):
    if payload.variance_quantity == 0:
        raise HTTPException(400, "variance_quantity cannot be zero")
    data = _run(supabase.table("sitemgr_material_discrepancies").insert(payload.model_dump()))
    return data[0]


@app.get("/discrepancies", response_model=List[s.DiscrepancyOut])
def list_discrepancies(project_id: Optional[str] = Query(None), material_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_material_discrepancies").select("*").order("created_at", desc=True)
    if project_id:
        q = q.eq("project_id", project_id)
    if material_id:
        q = q.eq("material_id", material_id)
    return _run(q) or []


# =============================================================================
# LABOR
# =============================================================================
@app.get("/labor", response_model=List[s.LaborOut])
def list_labor(project_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_labor").select("*").order("name")
    if project_id:
        q = q.eq("project_id", project_id)
    return _run(q)


@app.post("/labor", response_model=s.LaborOut)
def create_labor(payload: s.LaborCreate):
    if payload.worker_type not in ("Per-Day", "Piece-Work", "Subcontractor"):
        raise HTTPException(400, "Invalid worker_type")
    data = _run(supabase.table("sitemgr_labor").insert(payload.model_dump()))
    return data[0]


@app.post("/labor/{labor_id}/attendance", response_model=s.LaborAttendanceOut)
def record_attendance(labor_id: str, payload: s.LaborAttendanceCreate):
    if payload.labor_id != labor_id:
        raise HTTPException(400, "labor_id mismatch")
    body = _serialize_date_fields(payload.model_dump())
    if payload.attendance_status not in ("Present", "Absent", "Half Day", "Leave", "Unverified"):
        raise HTTPException(400, "Invalid attendance_status")
    data = _run(supabase.table("sitemgr_labor_attendance").insert(body))
    return data[0]


@app.post("/labor/piece-work", response_model=s.PieceWorkOut)
def create_piece_work(payload: s.PieceWorkCreate):
    if payload.quantity <= 0 or payload.unit_rate < 0:
        raise HTTPException(400, "quantity must be positive and unit_rate cannot be negative")
    if payload.status not in ("Pending", "Verified", "Rejected"):
        raise HTTPException(400, "Invalid piece-work status")
    body = _serialize_date_fields(payload.model_dump())
    body["total_amount"] = payload.quantity * payload.unit_rate
    data = _run(supabase.table("sitemgr_labor_piece_work").insert(body))
    return data[0]


@app.get("/labor/piece-work", response_model=List[s.PieceWorkOut])
def list_piece_work(project_id: Optional[str] = Query(None), labor_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_labor_piece_work").select("*").order("work_date", desc=True)
    if project_id:
        q = q.eq("project_id", project_id)
    if labor_id:
        q = q.eq("labor_id", labor_id)
    return _run(q) or []


@app.get("/labor/{labor_id}/attendance", response_model=List[s.LaborAttendanceOut])
def list_attendance(labor_id: str):
    return _run(
        supabase.table("sitemgr_labor_attendance")
        .select("*")
        .eq("labor_id", labor_id)
        .order("work_date", desc=True)
    )


@app.get("/labor/{labor_id}/balance")
def labor_balance(labor_id: str):
    labor = _run(supabase.table("sitemgr_labor").select("*").eq("id", labor_id))
    if not labor:
        raise HTTPException(404, "Worker/crew not found")
    daily_rate = labor[0]["daily_rate"]

    attendance = _run(
        supabase.table("sitemgr_labor_attendance").select("*").eq("labor_id", labor_id)
    )
    total_days = sum(a["days_worked"] for a in attendance)
    total_advances = sum(a["advance_paid"] for a in attendance)
    earned = total_days * daily_rate
    return {
        "labor_id": labor_id,
        "days_worked": total_days,
        "advances_paid": total_advances,
        "earned": earned,
        "balance_due": earned - total_advances,
    }


# =============================================================================
# SITE REPORTS
# =============================================================================
@app.get("/site-reports", response_model=List[s.SiteReportOut])
def list_site_reports(project_id: Optional[str] = Query(None)):
    q = supabase.table("sitemgr_site_reports").select("*").order("report_date", desc=True)
    if project_id:
        q = q.eq("project_id", project_id)
    return _run(q)


@app.post("/site-reports", response_model=s.SiteReportOut)
def create_site_report(payload: s.SiteReportCreate):
    body = _serialize_date_fields(payload.model_dump())
    data = _run(supabase.table("sitemgr_site_reports").insert(body))
    return data[0]


# =============================================================================
# FILE UPLOADS (receipts / site photos) -> Supabase Storage
# =============================================================================
@app.post("/uploads")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    path = f"{date.today().isoformat()}/{file.filename}"
    supabase.storage.from_("sitemgr-uploads").upload(
        path, contents, {"content-type": file.content_type or "application/octet-stream"}
    )
    public_url = supabase.storage.from_("sitemgr-uploads").get_public_url(path)
    return {"url": public_url, "path": path}


# =============================================================================
# DASHBOARD
# =============================================================================
@app.get("/dashboard/summary", response_model=s.DashboardSummary)
def dashboard_summary(project_id: Optional[str] = Query(None)):
    proj_q = supabase.table("sitemgr_projects").select("*")
    if project_id:
        proj_q = proj_q.eq("id", project_id)
    projects = _run(proj_q) or []
    total_budget = sum(float(p.get("budget") or 0) for p in projects)

    txn_q = supabase.table("sitemgr_transactions").select("*")
    if project_id:
        txn_q = txn_q.eq("project_id", project_id)
    transactions = _run(txn_q) or []
    total_spent = sum(float(t.get("amount") or 0) for t in transactions)

    spend_by_category = {}
    for t in transactions:
        category = t.get("category") or "Other"
        spend_by_category[category] = spend_by_category.get(category, 0) + float(
            t.get("amount") or 0
        )

    def normalized_category(transaction):
        return (transaction.get("category") or "").strip().lower().replace("_", " ").replace("-", " ")

    materials_spending = 0
    labour_spending = 0
    for transaction in transactions:
        category = normalized_category(transaction)
        amount = float(transaction.get("amount") or 0)
        if "material" in category:
            materials_spending += amount
        elif "labor" in category or "labour" in category:
            labour_spending += amount

    other_spending = total_spent - materials_spending - labour_spending
    budget_percentage = (total_spent / total_budget * 100) if total_budget else 0

    # Simple even-split placeholder for budget-by-category; refine once you
    # decide how project budgets should be broken down by category.
    budget_by_category = {}

    today = date.today().isoformat()
    materials_q = supabase.table("sitemgr_materials").select("*")
    if project_id:
        materials_q = materials_q.eq("project_id", project_id)
    materials = _run(materials_q) or []
    low_stock_materials = [
        {
            "id": material.get("id"),
            "item": material.get("item") or "Unnamed material",
            "in_stock": float(material.get("in_stock") or 0),
            "unit": material.get("unit") or "Units",
            "low_stock_threshold": float(material.get("low_stock_threshold") or 0),
        }
        for material in materials
        if float(material.get("in_stock") or 0)
        <= float(material.get("low_stock_threshold") or 0)
    ]

    labor_q = supabase.table("sitemgr_labor").select("id")
    if project_id:
        labor_q = labor_q.eq("project_id", project_id)
    labor = _run(labor_q) or []
    labor_ids = {worker.get("id") for worker in labor}

    att_q = supabase.table("sitemgr_labor_attendance").select("*").eq("work_date", today)
    attendance_today = _run(att_q) or []
    if project_id:
        attendance_today = [a for a in attendance_today if a.get("labor_id") in labor_ids]
    active_workers_today = len({a.get("labor_id") for a in attendance_today if a.get("labor_id")})

    return s.DashboardSummary(
        total_budget=total_budget,
        total_spent=total_spent,
        remaining_balance=total_budget - total_spent,
        active_workers_today=active_workers_today,
        spend_by_category=spend_by_category,
        budget_by_category=budget_by_category,
        total_project_value=total_budget,
        materials_spending=materials_spending,
        labour_spending=labour_spending,
        other_spending=other_spending,
        budget_percentage=budget_percentage,
        low_stock_material_count=len(low_stock_materials),
        low_stock_materials=low_stock_materials,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# =============================================================================
# AI ASSISTANT (DeepSeek)
# =============================================================================
@app.post("/ai/ask", response_model=s.AIAnswer)
def ask_ai(payload: s.AIAsk):
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "question is required")
    if len(question) > 4000:
        raise HTTPException(400, "question is too long")

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise HTTPException(
            503,
            "DeepSeek is not configured. Add DEEPSEEK_API_KEY to backend/.env and restart the backend.",
        )

    project_query = supabase.table("sitemgr_projects").select("*")
    if payload.project_id:
        project_query = project_query.eq("id", payload.project_id)
    projects = _run(project_query) or []

    transaction_query = supabase.table("sitemgr_transactions").select("*")
    if payload.project_id:
        transaction_query = transaction_query.eq("project_id", payload.project_id)
    transactions = _run(transaction_query) or []

    material_query = supabase.table("sitemgr_materials").select("*")
    if payload.project_id:
        material_query = material_query.eq("project_id", payload.project_id)
    materials = _run(material_query) or []

    labor_query = supabase.table("sitemgr_labor").select("*")
    if payload.project_id:
        labor_query = labor_query.eq("project_id", payload.project_id)
    labor = _run(labor_query) or []
    labor_ids = {worker.get("id") for worker in labor}

    attendance_today = _run(
        supabase.table("sitemgr_labor_attendance")
        .select("*")
        .eq("work_date", date.today().isoformat())
    ) or []
    if payload.project_id:
        attendance_today = [
            row for row in attendance_today if row.get("labor_id") in labor_ids
        ]

    report_query = supabase.table("sitemgr_site_reports").select("*").order(
        "report_date", desc=True
    ).limit(10)
    if payload.project_id:
        report_query = report_query.eq("project_id", payload.project_id)
    reports = _run(report_query) or []

    context = {
        "projects": projects,
        "transactions": transactions,
        "materials": materials,
        "workers": labor,
        "attendance_today": attendance_today,
        "recent_site_reports": reports,
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are the construction CRM assistant for a contractor. "
                "Answer using only the supplied live CRM data. Do not invent "
                "amounts, workers, materials, dates, or project facts. "
                "Use KSh for money. If the data does not answer the question, "
                "say what is missing. Keep answers practical and concise."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Live CRM data:\n{json.dumps(context, default=str)}\n\n"
                f"Question: {question}"
            ),
        },
    ]
    request_body = json.dumps(
        {"model": "deepseek-v4-flash", "messages": messages, "stream": False}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=request_body,
        headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result.get("choices", [{}])[0].get("message", {}).get("content")
        if not answer:
            raise HTTPException(502, "DeepSeek returned an empty answer")
        return s.AIAnswer(answer=answer)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise HTTPException(502, f"DeepSeek request failed: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(502, "Could not reach DeepSeek") from exc


def _payroll_calculation(project_id: str, period_start: date, period_end: date):
    labor = _run(
        supabase.table("sitemgr_labor")
        .select("*")
        .eq("project_id", project_id)
        .order("name")
    ) or []
    if not labor:
        return []

    attendance = _run(supabase.table("sitemgr_labor_attendance").select("*")) or []
    labor_ids = {worker.get("id") for worker in labor}
    attendance_by_labor = {labor_id: [] for labor_id in labor_ids}
    for row in attendance:
        if row.get("labor_id") not in labor_ids:
            continue
        try:
            work_date = date.fromisoformat(str(row.get("work_date"))[:10])
        except (TypeError, ValueError):
            continue
        if period_start <= work_date <= period_end:
            attendance_by_labor[row["labor_id"]].append(row)

    piece_work = _run(
        supabase.table("sitemgr_labor_piece_work")
        .select("labor_id, quantity, unit_rate, total_amount, status, work_date")
        .eq("project_id", project_id)
    ) or []
    piece_by_labor = {labor_id: 0.0 for labor_id in labor_ids}
    for row in piece_work:
        try:
            work_date = date.fromisoformat(str(row.get("work_date"))[:10])
        except (TypeError, ValueError):
            continue
        if period_start <= work_date <= period_end and row.get("status") == "Verified":
            amount = row.get("total_amount")
            if amount is None:
                amount = float(row.get("quantity") or 0) * float(row.get("unit_rate") or 0)
            piece_by_labor[row.get("labor_id")] = piece_by_labor.get(row.get("labor_id"), 0) + float(amount)

    rows = []
    for worker in labor:
        worker_attendance = attendance_by_labor.get(worker.get("id"), [])
        days_worked = sum(float(row.get("days_worked") or 0) for row in worker_attendance)
        advances = sum(float(row.get("advance_paid") or 0) for row in worker_attendance)
        gross_amount = days_worked * float(worker.get("daily_rate") or 0)
        piece_work_amount = piece_by_labor.get(worker.get("id"), 0)
        gross_amount += piece_work_amount
        if gross_amount <= 0:
            continue
        rows.append(
            {
                "project_id": project_id,
                "labor_id": worker["id"],
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "days_worked": days_worked,
                "gross_amount": gross_amount,
                "piece_work_amount": piece_work_amount,
                "advances": advances,
                "net_amount": max(gross_amount - advances, 0),
                "status": "Draft",
            }
        )
    return rows


@app.get("/labor/payroll/preview")
def payroll_preview(
    project_id: str = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
):
    if period_end - period_start != timedelta(days=6):
        raise HTTPException(400, "Payroll period must be exactly seven days")
    rows = _payroll_calculation(project_id, period_start, period_end)
    labor = _run(supabase.table("sitemgr_labor").select("id, name").eq("project_id", project_id)) or []
    names = {worker["id"]: worker["name"] for worker in labor}
    return [{**row, "labor_name": names.get(row["labor_id"], "Unknown worker")} for row in rows]


@app.get("/labor/payroll", response_model=List[s.PayrollOut])
def list_payroll(
    project_id: Optional[str] = Query(None),
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
):
    q = supabase.table("sitemgr_labor_payroll").select("*").order("period_start", desc=True)
    if project_id:
        q = q.eq("project_id", project_id)
    if period_start:
        q = q.eq("period_start", period_start.isoformat())
    if period_end:
        q = q.eq("period_end", period_end.isoformat())
    return _run(q) or []


@app.post("/labor/payroll", response_model=List[s.PayrollOut])
def generate_payroll(payload: s.PayrollGenerate):
    if payload.period_end - payload.period_start != timedelta(days=6):
        raise HTTPException(400, "Payroll period must be exactly seven days")
    rows = _payroll_calculation(payload.project_id, payload.period_start, payload.period_end)
    if not rows:
        raise HTTPException(400, "No attendance or advances found for this payroll week")

    existing = _run(
        supabase.table("sitemgr_labor_payroll")
        .select("id")
        .eq("project_id", payload.project_id)
        .eq("period_start", payload.period_start.isoformat())
        .eq("period_end", payload.period_end.isoformat())
    ) or []
    if existing:
        raise HTTPException(409, "Payroll has already been generated for this week")

    return _run(supabase.table("sitemgr_labor_payroll").insert(rows)) or []


@app.post("/labor/payroll/{payroll_id}/approve", response_model=s.PayrollOut)
def approve_payroll(payroll_id: str, payload: s.PayrollApprove):
    if not payload.approved_by.strip():
        raise HTTPException(400, "approved_by is required")
    payroll = _run(supabase.table("sitemgr_labor_payroll").select("*").eq("id", payroll_id)) or []
    if not payroll:
        raise HTTPException(404, "Payroll record not found")
    if payroll[0]["status"] != "Draft":
        raise HTTPException(400, "Only draft payroll can be approved")
    updated = _run(
        supabase.table("sitemgr_labor_payroll")
        .update({"status": "Approved", "approved_by": payload.approved_by.strip(), "approved_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", payroll_id)
    ) or []
    return updated[0]


@app.post("/labor/payroll/{payroll_id}/pay", response_model=s.PayrollOut)
def pay_payroll(payroll_id: str, payload: s.PayrollPay):
    if payload.payment_method not in ("M-Pesa", "Bank", "Cash", "Other"):
        raise HTTPException(400, "Invalid payment method")
    if not payload.payment_reference.strip() or not payload.paid_by.strip():
        raise HTTPException(400, "payment_reference and paid_by are required")
    payroll = _run(supabase.table("sitemgr_labor_payroll").select("*").eq("id", payroll_id)) or []
    if not payroll:
        raise HTTPException(404, "Payroll record not found")
    row = payroll[0]
    if row["status"] == "Paid":
        raise HTTPException(409, "This payroll has already been paid")
    if row["status"] != "Approved":
        raise HTTPException(400, "Payroll must be approved before payment")

    worker = _run(supabase.table("sitemgr_labor").select("name").eq("id", row["labor_id"])) or []
    worker_name = worker[0].get("name", "Worker") if worker else "Worker"
    _run(
        supabase.table("sitemgr_transactions").insert(
            {
                "project_id": row["project_id"],
                "txn_date": date.today().isoformat(),
                "category": "Labor Payment",
                "amount": float(row["net_amount"] or 0),
                "payee": worker_name,
                "notes": f"Payroll {row['period_start']} to {row['period_end']} | {payload.payment_reference.strip()}",
                "source_payroll_id": payroll_id,
            }
        )
    )
    updated = _run(
        supabase.table("sitemgr_labor_payroll")
        .update(
            {
                "status": "Paid",
                "payment_method": payload.payment_method,
                "payment_reference": payload.payment_reference.strip(),
                "paid_by": payload.paid_by.strip(),
                "paid_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", payroll_id)
    ) or []
    return updated[0]

# --- CORS MIDDLEWARE SETUP ---
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

