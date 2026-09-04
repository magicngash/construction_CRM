-- Construction CRM controls upgrade
-- Run this once in Supabase SQL Editor before using the new workflows.

alter table public.sitemgr_material_movements
  add column if not exists event_date date default current_date,
  add column if not exists condition text default 'Good',
  add column if not exists receiver_name text,
  add column if not exists checker_name text,
  add column if not exists recipient_name text,
  add column if not exists work_area text,
  add column if not exists evidence_url text,
  add column if not exists delivery_note_url text;

alter table public.sitemgr_labor
  add column if not exists contact_number text,
  add column if not exists worker_type text default 'Per-Day',
  add column if not exists pay_period text default 'Weekly',
  add column if not exists unit_rate numeric default 0;

alter table public.sitemgr_labor_attendance
  add column if not exists attendance_status text default 'Present',
  add column if not exists foreman_name text,
  add column if not exists site_location text;

alter table public.sitemgr_labor_payroll
  add column if not exists piece_work_amount numeric not null default 0;

create table if not exists public.sitemgr_material_audits (
  id uuid primary key default gen_random_uuid(),
  material_id uuid not null references public.sitemgr_materials(id),
  audit_date date not null,
  physical_count numeric not null check (physical_count >= 0),
  book_balance numeric not null,
  variance_quantity numeric not null,
  variance_flag boolean not null default false,
  counter_name text not null,
  witness_name text not null,
  signature text,
  status text not null default 'Open',
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.sitemgr_material_discrepancies (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.sitemgr_projects(id),
  material_id uuid not null references public.sitemgr_materials(id),
  stock_audit_id uuid references public.sitemgr_material_audits(id),
  linked_event_id uuid,
  reason text not null,
  variance_quantity numeric not null,
  evidence_url text,
  explanation text,
  reported_by text not null,
  approver_status text not null default 'Pending',
  approved_by text,
  created_at timestamptz not null default now()
);

create table if not exists public.sitemgr_labor_piece_work (
  id uuid primary key default gen_random_uuid(),
  labor_id uuid not null references public.sitemgr_labor(id),
  project_id uuid not null references public.sitemgr_projects(id),
  work_date date not null,
  task_completed text not null,
  work_area text,
  quantity numeric not null check (quantity > 0),
  unit text not null,
  unit_rate numeric not null check (unit_rate >= 0),
  total_amount numeric not null,
  verified_by text,
  status text not null default 'Pending',
  notes text,
  created_at timestamptz not null default now()
);

alter table public.sitemgr_material_audits enable row level security;
alter table public.sitemgr_material_discrepancies enable row level security;
alter table public.sitemgr_labor_piece_work enable row level security;

create index if not exists material_audits_material_date_idx
  on public.sitemgr_material_audits(material_id, audit_date desc);
create index if not exists material_discrepancies_project_idx
  on public.sitemgr_material_discrepancies(project_id, created_at desc);
create index if not exists piece_work_project_date_idx
  on public.sitemgr_labor_piece_work(project_id, work_date desc);
