from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel


# ---------- Projects ----------
class ProjectCreate(BaseModel):
    name: str
    location: Optional[str] = None
    budget: float = 0
    status: str = "Planning"
    notes: Optional[str] = None


class ProjectOut(ProjectCreate):
    id: str
    created_at: datetime


# ---------- Transactions ----------
class TransactionCreate(BaseModel):
    project_id: str
    txn_date: date
    category: str
    amount: float
    payee: Optional[str] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class TransactionOut(TransactionCreate):
    id: str
    created_at: datetime


# ---------- Materials ----------
class MaterialCreate(BaseModel):
    project_id: str
    item: str
    unit: str = "Units"
    in_stock: float = 0
    low_stock_threshold: float = 0
    # Used to audit opening stock; it is not stored as a material-table column.
    opening_stock_recorded_by: Optional[str] = None
    opening_stock_unit_cost: Optional[float] = None


class MaterialOut(MaterialCreate):
    id: str
    created_at: datetime


class MaterialMovementCreate(BaseModel):
    material_id: str
    movement_type: str  # "received" | "used"
    quantity: float
    unit_cost: float = 0
    supplier: Optional[str] = None
    reference: Optional[str] = None
    recorded_by: Optional[str] = None
    notes: Optional[str] = None
    event_date: Optional[date] = None
    condition: str = "Good"
    receiver_name: Optional[str] = None
    checker_name: Optional[str] = None
    recipient_name: Optional[str] = None
    work_area: Optional[str] = None
    evidence_url: Optional[str] = None
    delivery_note_url: Optional[str] = None


class MaterialMovementOut(MaterialMovementCreate):
    id: str
    moved_at: datetime


# ---------- Labor ----------
class LaborCreate(BaseModel):
    project_id: str
    name: str
    role: Optional[str] = None
    daily_rate: float = 0
    contact_number: Optional[str] = None
    worker_type: str = "Per-Day"
    pay_period: str = "Weekly"
    unit_rate: float = 0


class LaborOut(LaborCreate):
    id: str
    created_at: datetime


class LaborAttendanceCreate(BaseModel):
    labor_id: str
    work_date: date
    days_worked: float = 1
    advance_paid: float = 0
    attendance_status: str = "Present"
    foreman_name: Optional[str] = None
    site_location: Optional[str] = None


class LaborAttendanceOut(LaborAttendanceCreate):
    id: str
    created_at: datetime


# ---------- Site Reports ----------
class SiteReportCreate(BaseModel):
    project_id: str
    report_date: date
    foreman_name: Optional[str] = None
    work_completed: Optional[str] = None
    headcount: int = 0
    materials_consumed: Optional[str] = None
    delays_issues: Optional[str] = None
    photo_urls: List[str] = []


class SiteReportOut(SiteReportCreate):
    id: str
    created_at: datetime


# ---------- Dashboard ----------
class DashboardSummary(BaseModel):
    total_budget: float
    total_spent: float
    remaining_balance: float
    active_workers_today: int
    spend_by_category: dict
    budget_by_category: dict
    # Extended dashboard fields. Defaults keep the response tolerant of older
    # callers while the existing fields above remain unchanged.
    total_project_value: float = 0
    materials_spending: float = 0
    labour_spending: float = 0
    other_spending: float = 0
    budget_percentage: float = 0
    low_stock_material_count: int = 0
    low_stock_materials: List[dict] = []


# ---------- AI Assistant ----------
class AIAsk(BaseModel):
    question: str
    project_id: Optional[str] = None


class AIAnswer(BaseModel):
    answer: str


# ---------- Weekly Labour Payroll ----------
class PayrollGenerate(BaseModel):
    project_id: str
    period_start: date
    period_end: date


class PayrollApprove(BaseModel):
    approved_by: str


class PayrollPay(BaseModel):
    payment_method: str
    payment_reference: str
    paid_by: str


class PayrollOut(BaseModel):
    id: str
    project_id: str
    labor_id: str
    period_start: date
    period_end: date
    days_worked: float
    gross_amount: float
    advances: float
    net_amount: float
    piece_work_amount: float = 0
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    paid_by: Optional[str] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class PieceWorkCreate(BaseModel):
    labor_id: str
    project_id: str
    work_date: date
    task_completed: str
    quantity: float
    unit: str
    unit_rate: float
    work_area: Optional[str] = None
    verified_by: Optional[str] = None
    status: str = "Pending"
    notes: Optional[str] = None


class PieceWorkOut(PieceWorkCreate):
    id: str
    total_amount: float = 0
    created_at: datetime


class StockAuditCreate(BaseModel):
    material_id: str
    audit_date: date
    physical_count: float
    counter_name: str
    witness_name: str
    signature: Optional[str] = None
    notes: Optional[str] = None


class StockAuditOut(StockAuditCreate):
    id: str
    book_balance: float
    variance_quantity: float
    variance_flag: bool
    status: str = "Open"
    created_at: datetime


class DiscrepancyCreate(BaseModel):
    project_id: str
    material_id: str
    stock_audit_id: Optional[str] = None
    linked_event_id: Optional[str] = None
    reason: str
    variance_quantity: float
    evidence_url: Optional[str] = None
    explanation: Optional[str] = None
    reported_by: str
    approver_status: str = "Pending"
    approved_by: Optional[str] = None


class DiscrepancyOut(DiscrepancyCreate):
    id: str
    created_at: datetime
