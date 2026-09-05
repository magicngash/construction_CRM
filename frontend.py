import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


# =============================================================================
# CONFIG
# =============================================================================

API_BASE = os.environ.get(
    "SITEMGR_API_BASE",
    "https://construction-crm-zdqc.onrender.com",
).rstrip("/")

st.set_page_config(
    page_title="Contractor Site Manager",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# HELPERS
# =============================================================================

def money(value):
    try:
        return f"KSh {float(value):,.0f}"
    except (TypeError, ValueError):
        return "KSh 0"


def money_decimal(value):
    try:
        return f"KSh {float(value):,.2f}"
    except (TypeError, ValueError):
        return "KSh 0.00"


def format_datetime(value):
    """Format API timestamps for people reading the stock history."""
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(ZoneInfo("Africa/Nairobi"))
        day = parsed.day
        if 10 < day % 100 < 14:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{parsed.strftime('%b')} {day}{suffix}, {parsed.year}, {parsed.strftime('%I:%M %p').lstrip('0')}"
    except (TypeError, ValueError):
        return str(value)


def api_get(path, params=None):
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
        return None


def api_post(path, json=None, files=None):
    try:
        response = requests.post(
            f"{API_BASE}{path}",
            json=json,
            files=files,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
        return None


def api_patch(path, json=None):
    try:
        response = requests.patch(
            f"{API_BASE}{path}",
            json=json,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
        return None


def api_delete(path):
    try:
        response = requests.delete(
            f"{API_BASE}{path}",
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
        return None


@st.cache_data(ttl=10)
def get_projects():
    return api_get("/projects") or []


def project_map(projects):
    return {p["name"]: p["id"] for p in projects}


def project_name(projects, project_id):
    for project in projects:
        if project["id"] == project_id:
            return project["name"]
    return "Unknown Project"


def refresh():
    st.cache_data.clear()
    st.rerun()


# =============================================================================
# LOAD PROJECTS
# =============================================================================

projects = get_projects()


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.title("🏗️ Site Manager")
    st.caption("Construction business operating system")

    st.markdown("---")

    st.subheader("Project Context")

    project_options = ["All Projects"] + [
        p["name"] for p in projects
    ]

    selected_project = st.selectbox(
        "Active Project",
        project_options,
    )

    selected_project_id = None

    if selected_project != "All Projects":
        selected_project_id = project_map(projects).get(selected_project)

    st.markdown("---")

    if st.button("🔄 Refresh Data", use_container_width=True):
        refresh()

    st.markdown("---")

    st.caption("Contractor Site Manager")
    st.caption("MVP v1.0")


# =============================================================================
# NAVIGATION
# =============================================================================

navigation = st.radio(
    "Navigation",
    [
        "📊 Dashboard",
        "📁 Projects",
        "💳 Money",
        "📦 Materials",
        "👷 Labour",
        "📝 Site Reports",
        "🤖 AI Assistant",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("---")


# =============================================================================
# DASHBOARD
# =============================================================================

if navigation == "📊 Dashboard":

    st.title("📊 Project Dashboard")

    if selected_project == "All Projects":
        st.caption("Overview across all projects")
    else:
        st.caption(f"Active project: {selected_project}")

    summary_params = {}

    if selected_project_id:
        summary_params["project_id"] = selected_project_id

    summary = api_get(
        "/dashboard/summary",
        params=summary_params or None,
    )

    if not summary:
        st.warning("Could not load dashboard data.")
        st.stop()

    total_budget = summary.get("total_project_value", summary.get("total_budget", 0))
    total_spent = summary.get("total_spent", 0)
    remaining = summary.get("remaining_balance", 0)
    workers_today = summary.get("active_workers_today", 0)
    budget_percentage = summary.get("budget_percentage", 0)
    materials_spending = summary.get("materials_spending", 0)
    labour_spending = summary.get("labour_spending", 0)
    other_spending = summary.get("other_spending", 0)
    low_stock_materials = summary.get("low_stock_materials", []) or []

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Project Value",
        money(total_budget),
    )

    col2.metric(
        "Total Spent",
        money(total_spent),
    )

    col3.metric(
        "Balance Remaining",
        money(remaining),
    )

    col4.metric(
        "Budget Used %",
        f"{float(budget_percentage):.1f}%",
    )

    st.progress(min(max(float(budget_percentage) / 100, 0), 1))

    st.markdown("---")

    st.subheader("💰 Cost Breakdown")
    cost1, cost2, cost3 = st.columns(3)
    cost1.metric("Materials", money(materials_spending))
    cost2.metric("Labour", money(labour_spending))
    cost3.metric("Other Expenses", money(other_spending))

    st.markdown("---")

    status_left, status_right = st.columns([1, 2])
    with status_left:
        st.subheader("📍 Site Status")
        st.metric("Workers Today", workers_today)
        st.metric("Low-stock Materials", summary.get("low_stock_material_count", len(low_stock_materials)))

    with status_right:
        st.subheader("⚠️ Low-stock Materials")
        if low_stock_materials:
            low_stock_rows = [
                {
                    "Material": material.get("item", "—"),
                    "Stock": f"{material.get('in_stock', 0):g} {material.get('unit', '')}".strip(),
                    "Threshold": f"{material.get('low_stock_threshold', 0):g} {material.get('unit', '')}".strip(),
                }
                for material in low_stock_materials
            ]
            st.dataframe(pd.DataFrame(low_stock_rows), use_container_width=True, hide_index=True)
        else:
            st.success("All tracked materials are above their low-stock thresholds.")

    st.markdown("---")

    left, right = st.columns([2, 1])

    with left:
        st.subheader("💰 Spending by Category")

        spend = summary.get("spend_by_category", {})

        if spend:
            chart_df = pd.DataFrame(
                {
                    "Category": list(spend.keys()),
                    "Amount": list(spend.values()),
                }
            )

            st.bar_chart(
                chart_df.set_index("Category")
            )
        else:
            st.info("No spending recorded yet.")

    with right:
        st.subheader("📈 Budget Position")

        if total_budget > 0:
            percentage = float(budget_percentage)

            st.metric(
                "Budget Used",
                f"{percentage:.1f}%",
            )

            st.progress(
                min(max(percentage / 100, 0), 1)
            )

            if percentage > 100:
                st.error("⚠️ Project is over budget.")
            elif percentage >= 80:
                st.warning("⚠️ More than 80% of budget used.")
            else:
                st.success("Budget position looks healthy.")
        else:
            st.info("Set a project budget to see budget tracking.")

    st.markdown("---")

    st.subheader("💳 Recent Transactions")

    transaction_params = {}

    if selected_project_id:
        transaction_params["project_id"] = selected_project_id

    transactions = api_get(
        "/transactions",
        params=transaction_params or None,
    ) or []

    if transactions:
        names = {
            p["id"]: p["name"]
            for p in projects
        }

        rows = []

        for transaction in transactions[:10]:
            rows.append(
                {
                    "Date": transaction.get("txn_date"),
                    "Project": names.get(
                        transaction.get("project_id"),
                        "—",
                    ),
                    "Category": transaction.get("category"),
                    "Payee": transaction.get("payee") or "—",
                    "Amount": money_decimal(
                        transaction.get("amount", 0)
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No transactions recorded yet.")


# =============================================================================
# PROJECTS
# =============================================================================

elif navigation == "📁 Projects":

    st.title("📁 Projects")

    tab_list, tab_create = st.tabs(
        ["Project List", "➕ New Project"]
    )

    with tab_list:

        if not projects:
            st.info("No projects yet. Create your first project.")
        else:

            for project in projects:

                with st.container(border=True):

                    col1, col2, col3 = st.columns([3, 2, 1])

                    with col1:
                        st.subheader(project["name"])
                        st.write(
                            project.get("location")
                            or "No location specified"
                        )

                    with col2:
                        st.write(
                            f"**Budget:** {money(project.get('budget', 0))}"
                        )
                        st.write(
                            f"**Status:** {project.get('status', '—')}"
                        )

                    with col3:
                        st.write("")

                        if st.button(
                            "Open",
                            key=f"open_project_{project['id']}",
                            use_container_width=True,
                        ):
                            st.session_state[
                                "selected_project_from_button"
                            ] = project["id"]

                    if project.get("notes"):
                        st.caption(project["notes"])

                    edit_key = f"edit_project_{project['id']}"

                    with st.expander("Edit Project"):

                        with st.form(edit_key):

                            edit_name = st.text_input(
                                "Project Name",
                                value=project["name"],
                            )

                            edit_location = st.text_input(
                                "Location",
                                value=project.get("location") or "",
                            )

                            edit_budget = st.number_input(
                                "Budget",
                                min_value=0.0,
                                value=float(project.get("budget", 0)),
                                step=1000.0,
                            )

                            edit_status = st.selectbox(
                                "Status",
                                [
                                    "Planning",
                                    "In Progress",
                                    "Complete",
                                ],
                                index=[
                                    "Planning",
                                    "In Progress",
                                    "Complete",
                                ].index(
                                    project.get(
                                        "status",
                                        "Planning",
                                    )
                                )
                                if project.get("status") in [
                                    "Planning",
                                    "In Progress",
                                    "Complete",
                                ]
                                else 0,
                            )

                            edit_notes = st.text_area(
                                "Notes",
                                value=project.get("notes") or "",
                            )

                            save = st.form_submit_button(
                                "Save Changes"
                            )

                            if save:

                                result = api_patch(
                                    f"/projects/{project['id']}",
                                    json={
                                        "name": edit_name,
                                        "location": edit_location,
                                        "budget": edit_budget,
                                        "status": edit_status,
                                        "notes": edit_notes,
                                    },
                                )

                                if result:
                                    st.success(
                                        "Project updated."
                                    )
                                    refresh()

                    if st.button(
                        "🗑️ Delete Project",
                        key=f"delete_project_{project['id']}",
                    ):

                        result = api_delete(
                            f"/projects/{project['id']}"
                        )

                        if result:
                            st.success("Project deleted.")
                            refresh()

    with tab_create:

        st.subheader("Create Construction Project")

        with st.form("create_project"):

            name = st.text_input(
                "Project Name",
                placeholder="e.g. Runda Residence",
            )

            location = st.text_input(
                "Site Location",
                placeholder="e.g. Runda, Nairobi",
            )

            budget = st.number_input(
                "Project Budget",
                min_value=0.0,
                step=1000.0,
            )

            status = st.selectbox(
                "Status",
                [
                    "Planning",
                    "In Progress",
                    "Complete",
                ],
            )

            notes = st.text_area(
                "Scope / Notes"
            )

            submit = st.form_submit_button(
                "Create Project",
                use_container_width=True,
            )

            if submit:

                if not name.strip():
                    st.error("Project name is required.")

                else:

                    result = api_post(
                        "/projects",
                        json={
                            "name": name.strip(),
                            "location": location.strip(),
                            "budget": budget,
                            "status": status,
                            "notes": notes.strip(),
                        },
                    )

                    if result:
                        st.success(
                            f"Project '{name}' created."
                        )
                        refresh()


# =============================================================================
# MONEY / TRANSACTIONS
# =============================================================================

elif navigation == "💳 Money":

    st.title("💳 Money")

    tab_entry, tab_history = st.tabs(
        [
            "➕ Record Transaction",
            "📋 Transaction History",
        ]
    )

    with tab_entry:

        if not projects:
            st.warning(
                "Create a project before recording transactions."
            )

        else:

            st.subheader("Fast Expense Entry")

            with st.form(
                "transaction_form",
                clear_on_submit=True,
            ):

                col1, col2 = st.columns(2)

                with col1:

                    transaction_date = st.date_input(
                        "Date",
                        datetime.now(),
                    )

                    project_names = [
                        p["name"] for p in projects
                    ]

                    default_project_index = 0

                    if selected_project in project_names:
                        default_project_index = (
                            project_names.index(
                                selected_project
                            )
                        )

                    transaction_project = st.selectbox(
                        "Project",
                        project_names,
                        index=default_project_index,
                    )

                    category = st.selectbox(
                        "Category",
                        [
                            "Materials",
                            "Labor Payment",
                            "Equipment",
                            "Transport",
                            "Misc",
                        ],
                    )

                with col2:

                    amount = st.number_input(
                        "Amount (KSh)",
                        min_value=0.0,
                        step=100.0,
                    )

                    payee = st.text_input(
                        "Payee / Supplier / Worker"
                    )

                    receipt = st.file_uploader(
                        "Receipt",
                        type=[
                            "jpg",
                            "jpeg",
                            "png",
                            "pdf",
                        ],
                    )

                notes = st.text_input(
                    "Notes"
                )

                submit = st.form_submit_button(
                    "Record Transaction",
                    use_container_width=True,
                )

                if submit:

                    if amount <= 0:
                        st.error(
                            "Enter an amount greater than zero."
                        )

                    else:

                        receipt_url = None

                        if receipt:

                            upload = api_post(
                                "/uploads",
                                files={
                                    "file": (
                                        receipt.name,
                                        receipt.getvalue(),
                                        receipt.type,
                                    )
                                },
                            )

                            if upload:
                                receipt_url = upload.get("url")

                        project_id = project_map(
                            projects
                        )[transaction_project]

                        result = api_post(
                            "/transactions",
                            json={
                                "project_id": project_id,
                                "txn_date": transaction_date.isoformat(),
                                "category": category,
                                "amount": amount,
                                "payee": payee,
                                "notes": notes,
                                "receipt_url": receipt_url,
                            },
                        )

                        if result:
                            st.success(
                                "Transaction recorded successfully."
                            )
                            st.cache_data.clear()

    with tab_history:

        params = {}

        if selected_project_id:
            params["project_id"] = selected_project_id

        transactions = api_get(
            "/transactions",
            params=params or None,
        ) or []

        if not transactions:
            st.info("No transactions recorded.")
        else:

            names = {
                p["id"]: p["name"]
                for p in projects
            }

            rows = []

            for transaction in transactions:

                rows.append(
                    {
                        "Date": transaction.get("txn_date"),
                        "Project": names.get(
                            transaction.get("project_id"),
                            "—",
                        ),
                        "Category": transaction.get(
                            "category"
                        ),
                        "Payee": transaction.get(
                            "payee"
                        ) or "—",
                        "Amount": money_decimal(
                            transaction.get(
                                "amount",
                                0,
                            )
                        ),
                        "Notes": transaction.get(
                            "notes"
                        ) or "",
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )


# =============================================================================
# MATERIALS
# =============================================================================

elif navigation == "📦 Materials":

    st.title("📦 Materials")

    params = {}

    if selected_project_id:
        params["project_id"] = selected_project_id

    materials = api_get(
        "/materials",
        params=params or None,
    ) or []

    tab_stock, tab_add, tab_movement, tab_audit = st.tabs(
        [
            "📦 Stock",
            "➕ Add Material",
            "🔄 Stock Movement",
            "🧾 Daily Audit",
        ]
    )

    with tab_stock:

        if materials:

            rows = []

            for material in materials:

                stock = material.get(
                    "in_stock",
                    0,
                )

                threshold = material.get(
                    "low_stock_threshold",
                    0,
                )

                if stock <= threshold:
                    status = "🔴 LOW"
                else:
                    status = "🟢 OK"

                rows.append(
                    {
                        "Material": material.get(
                            "item"
                        ),
                        "Stock": stock,
                        "Unit": material.get(
                            "unit"
                        ),
                        "Threshold": threshold,
                        "Status": status,
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No materials tracked for this project."
            )

    with tab_add:

        if not projects:
            st.warning(
                "Create a project first."
            )

        else:

            with st.form("material_form", clear_on_submit=True):

                project_name_selected = st.selectbox(
                    "Project",
                    [p["name"] for p in projects],
                )

                item = st.text_input(
                    "Material",
                    placeholder="e.g. Cement",
                )

                unit = st.text_input(
                    "Unit",
                    value="Bags",
                )

                stock = st.number_input(
                    "Starting Stock",
                    min_value=0.0,
                    step=1.0,
                )

                opening_stock_unit_cost = st.number_input(
                    "Opening Stock Unit Cost (KSh)",
                    min_value=0.0,
                    step=10.0,
                    help="Required when starting stock is above zero.",
                )

                threshold = st.number_input(
                    "Low Stock Threshold",
                    min_value=0.0,
                    step=1.0,
                )

                opening_stock_recorded_by = st.text_input(
                    "Opening Stock Recorded by",
                    placeholder="Required when starting stock is above zero",
                )

                matching_material = next(
                    (
                        material
                        for material in materials
                        if material.get("project_id")
                        == project_map(projects).get(project_name_selected)
                        and material.get("item", "").strip().lower()
                        == item.strip().lower()
                    ),
                    None,
                )

                confirm_duplicate = False
                if matching_material and item.strip():
                    st.warning(
                        f"A material named '{matching_material.get('item')}' already exists "
                        "in this project. Add it only if this is intentionally a separate stock item."
                    )
                    confirm_duplicate = st.checkbox(
                        "I confirm this is not a duplicate material",
                        key="confirm_duplicate_material",
                    )

                submit = st.form_submit_button(
                    "Add Material",
                    use_container_width=True,
                )

                if submit:

                    if not item.strip():
                        st.error(
                            "Material name is required."
                        )

                    elif stock > 0 and not opening_stock_recorded_by.strip():
                        st.error(
                            "Enter who recorded the opening stock quantity."
                        )

                    elif matching_material and not confirm_duplicate:
                        st.error(
                            "Confirm that this is not a duplicate material before adding it."
                        )

                    else:

                        result = api_post(
                            "/materials",
                            json={
                                "project_id": project_map(
                                    projects
                                )[project_name_selected],
                                "item": item.strip(),
                                "unit": unit.strip(),
                                "in_stock": stock,
                                "low_stock_threshold": threshold,
                                "opening_stock_recorded_by": opening_stock_recorded_by.strip() or None,
                                "opening_stock_unit_cost": opening_stock_unit_cost if stock > 0 else None,
                            },
                        )

                        if result:
                            st.success(
                                f"{item} added to inventory."
                            )
                            st.cache_data.clear()

    with tab_movement:

        if not materials:
            st.info(
                "Add a material first."
            )

        else:

            material_lookup = {
                m["item"]: m
                for m in materials
            }

            selected_material_name = st.selectbox(
                "Material",
                list(material_lookup.keys()),
            )

            selected_material = material_lookup[
                selected_material_name
            ]

            st.write(
                f"Current stock: **"
                f"{selected_material.get('in_stock', 0)} "
                f"{selected_material.get('unit', '')}**"
            )

            movements = api_get(
                f"/materials/{selected_material['id']}/movements"
            ) or []

            with st.expander("Stock history", expanded=False):
                if movements:
                    movement_rows = [
                        {
                            "Date / Time": format_datetime(movement.get("moved_at")),
                            "Action": "Received" if movement.get("movement_type") == "received" else "Used on Site",
                            "Quantity": movement.get("quantity", 0),
                            "Unit Cost": money_decimal(movement.get("unit_cost", 0)),
                            "Total Cost": money_decimal(
                                float(movement.get("quantity", 0) or 0)
                                * float(movement.get("unit_cost", 0) or 0)
                            ),
                            "Recorded by": movement.get("recorded_by") or "—",
                            "Supplier": movement.get("supplier") or "—",
                            "Reference / Notes": " | ".join(
                                value
                                for value in [
                                    movement.get("reference"),
                                    movement.get("notes"),
                                ]
                                if value
                            ) or "—",
                        }
                        for movement in movements
                    ]
                    st.dataframe(
                        pd.DataFrame(movement_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No stock movements recorded yet.")

            with st.form("stock_movement_form", clear_on_submit=True):
                movement_type = st.radio(
                    "Movement",
                    [
                        "Received",
                        "Used on Site",
                    ],
                    horizontal=True,
                )

                quantity = st.number_input(
                    "Quantity",
                    min_value=0.0,
                    step=1.0,
                )

                event_date = st.date_input("Event date", datetime.now().date())

                unit_cost = st.number_input(
                    "Unit Cost (KSh)",
                    min_value=0.0,
                    step=10.0,
                    help="Required for received stock. Used stock uses weighted-average cost.",
                )

                supplier = st.text_input(
                    "Supplier",
                    placeholder="e.g. ABC Building Supplies",
                )

                receiver_name = st.text_input("Receiver name (delivery only)")
                checker_name = st.text_input("Checker name (delivery only)")
                recipient_name = st.text_input("Recipient / fundi / foreman (issuance only)")
                work_area = st.text_input("Specific work area (issuance only)", placeholder="e.g. Floor 1 slab")
                condition = st.selectbox("Delivery condition", ["Good", "Damaged"])

                reference = st.text_input(
                    "Delivery / Reference No.",
                    placeholder="e.g. Invoice 1042",
                )

                recorded_by = st.text_input(
                    "Received / Updated by",
                    placeholder="e.g. John Kamau",
                )

                movement_notes = st.text_input(
                    "Movement notes",
                    placeholder="e.g. Supplier delivery note or site usage",
                )

                confirm_movement = st.checkbox(
                    "I confirm this stock update is intentional and has not already been entered",
                )

                submit_movement = st.form_submit_button(
                    "Update Stock",
                    use_container_width=True,
                )

            if submit_movement:

                if quantity <= 0:
                    st.error("Enter a quantity greater than zero.")
                elif not recorded_by.strip():
                    st.error("Enter the name of the person receiving or updating the stock.")
                elif not confirm_movement:
                    st.warning(
                        "Please confirm this stock update is intentional before submitting."
                    )
                else:
                    api_type = (
                        "received"
                        if movement_type == "Received"
                        else "used"
                    )
                    note_parts = []
                    if movement_notes.strip():
                        note_parts.append(movement_notes.strip())

                    result = api_post(
                        f"/materials/{selected_material['id']}/movements",
                    json={
                        "material_id": selected_material["id"],
                        "movement_type": api_type,
                        "quantity": quantity,
                        "event_date": event_date.isoformat(),
                        "unit_cost": unit_cost if movement_type == "Received" else 0,
                        "supplier": supplier.strip() or None,
                        "reference": reference.strip() or None,
                        "recorded_by": recorded_by.strip() or None,
                        "receiver_name": receiver_name.strip() or None,
                        "checker_name": checker_name.strip() or None,
                        "recipient_name": recipient_name.strip() or None,
                        "work_area": work_area.strip() or None,
                        "condition": condition,
                            "notes": " | ".join(note_parts) or None,
                    },
                    )

                    if result:
                        st.success(
                            "Stock updated successfully and added to the stock history."
                        )
                        st.cache_data.clear()

    with tab_audit:
        if not materials:
            st.info("Add a material first.")
        else:
            audit_material_name = st.selectbox(
                "Material to count", [m["item"] for m in materials], key="audit_material"
            )
            audit_material = next(m for m in materials if m["item"] == audit_material_name)
            audit_date = st.date_input("Audit date", datetime.now().date(), key="audit_date")
            book = api_get(
                f"/materials/{audit_material['id']}/audit-book-balance",
                params={"audit_date": audit_date.isoformat()},
            ) or {}
            st.metric("System book balance", f"{book.get('book_balance', 0):g} {audit_material.get('unit', '')}")
            with st.form("stock_audit_form", clear_on_submit=True):
                physical_count = st.number_input("Physical count", min_value=0.0, step=1.0)
                counter_name = st.text_input("Counter name")
                witness_name = st.text_input("Witness name")
                signature = st.text_input("Sign-off signature / reference")
                audit_notes = st.text_input("Audit notes")
                submit_audit = st.form_submit_button("Lock daily stock audit", use_container_width=True)
            if submit_audit:
                audit = api_post(
                    f"/materials/{audit_material['id']}/audits",
                    json={
                        "material_id": audit_material["id"],
                        "audit_date": audit_date.isoformat(),
                        "physical_count": physical_count,
                        "counter_name": counter_name.strip(),
                        "witness_name": witness_name.strip(),
                        "signature": signature.strip() or None,
                        "notes": audit_notes.strip() or None,
                    },
                )
                if audit:
                    if audit.get("variance_flag"):
                        st.warning(f"Variance detected: {audit.get('variance_quantity', 0):g} {audit_material.get('unit', '')}. Create a discrepancy record for investigation.")
                    else:
                        st.success("Stock audit locked with no variance.")
            audits = api_get(f"/materials/{audit_material['id']}/audits") or []
            if audits:
                st.dataframe(pd.DataFrame([
                    {
                        "Date": row.get("audit_date"),
                        "Book": row.get("book_balance", 0),
                        "Physical": row.get("physical_count", 0),
                        "Variance": row.get("variance_quantity", 0),
                        "Counter": row.get("counter_name"),
                        "Witness": row.get("witness_name"),
                        "Status": row.get("status", "Open"),
                    } for row in audits
                ]), use_container_width=True, hide_index=True)


# =============================================================================
# LABOUR
# =============================================================================

elif navigation == "👷 Labour":

    st.title("👷 Labour")

    params = {}

    if selected_project_id:
        params["project_id"] = selected_project_id

    labor = api_get(
        "/labor",
        params=params or None,
    ) or []

    tab_roster, tab_add, tab_attendance, tab_piece_work, tab_payroll = st.tabs(
        [
            "👷 Crew Roster",
            "➕ Add Worker",
            "📅 Attendance & Advances",
            "💵 Weekly Payroll",
            "Piece Work",
        ]
    )

    with tab_roster:

        if labor:

            rows = []

            for worker in labor:

                balance = api_get(
                    f"/labor/{worker['id']}/balance"
                ) or {}

                rows.append(
                    {
                        "Worker / Crew": worker.get(
                            "name"
                        ),
                        "Role": worker.get(
                            "role"
                        ) or "—",
                        "Daily Rate": money(
                            worker.get(
                                "daily_rate",
                                0,
                            )
                        ),
                        "Days Worked": balance.get(
                            "days_worked",
                            0,
                        ),
                        "Earned": money(
                            balance.get(
                                "earned",
                                0,
                            )
                        ),
                        "Advances": money(
                            balance.get(
                                "advances_paid",
                                0,
                            )
                        ),
                        "Balance Due": money(
                            balance.get(
                                "balance_due",
                                0,
                            )
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No workers or crews have been added."
            )

    with tab_add:

        if not projects:
            st.warning(
                "Create a project first."
            )

        else:

            with st.form("labor_form"):

                project_name_selected = st.selectbox(
                    "Project",
                    [p["name"] for p in projects],
                )

                worker_name = st.text_input(
                    "Worker / Crew Name"
                )

                role = st.text_input(
                    "Role",
                    placeholder="e.g. Mason",
                )

                rate = st.number_input(
                    "Daily Rate (KSh)",
                    min_value=0.0,
                    step=100.0,
                )

                contact_number = st.text_input("Contact number")
                worker_type = st.selectbox("Worker type", ["Per-Day", "Piece-Work", "Subcontractor"])
                pay_period = st.selectbox("Pay period", ["Daily", "Weekly", "Monthly"])

                submit = st.form_submit_button(
                    "Add Worker / Crew",
                    use_container_width=True,
                )

                if submit:

                    if not worker_name.strip():
                        st.error(
                            "Worker name is required."
                        )

                    else:

                        result = api_post(
                            "/labor",
                            json={
                                "project_id": project_map(
                                    projects
                                )[project_name_selected],
                                "name": worker_name.strip(),
                                "role": role.strip(),
                                "daily_rate": rate,
                                "contact_number": contact_number.strip() or None,
                                "worker_type": worker_type,
                                "pay_period": pay_period,
                            },
                        )

                        if result:
                            st.success(
                                f"{worker_name} added."
                            )
                            st.cache_data.clear()

    with tab_attendance:

        if not labor:
            st.info(
                "Add a worker first."
            )

        else:

            workers = {
                w["name"]: w
                for w in labor
            }

            selected_worker_name = st.selectbox(
                "Worker / Crew",
                list(workers.keys()),
            )

            worker = workers[
                selected_worker_name
            ]

            work_date = st.date_input(
                "Work Date",
                datetime.now(),
            )

            days = st.number_input(
                "Days Worked",
                min_value=0.0,
                value=1.0,
                step=0.5,
            )

            advance = st.number_input(
                "Advance Paid (KSh)",
                min_value=0.0,
                step=100.0,
            )

            attendance_status = st.selectbox("Attendance status", ["Present", "Absent", "Half Day", "Leave", "Unverified"])
            foreman_name = st.text_input("Foreman sign-off")
            site_location = st.text_input("Site location")

            if st.button(
                "Log Attendance",
                use_container_width=True,
            ):

                result = api_post(
                    f"/labor/{worker['id']}/attendance",
                    json={
                        "labor_id": worker["id"],
                        "work_date": work_date.isoformat(),
                        "days_worked": days,
                        "advance_paid": advance,
                        "attendance_status": attendance_status,
                        "foreman_name": foreman_name.strip() or None,
                        "site_location": site_location.strip() or None,
                    },
                )

                if result:
                    st.success(
                        "Attendance recorded."
                    )
                    st.cache_data.clear()


    with st.expander("Piece-work / subcontractor log"):
        if not labor:
            st.info("Add a worker or subcontractor first.")
        else:
            piece_workers = {w["name"]: w for w in labor}
            with st.form("piece_work_form", clear_on_submit=True):
                piece_worker_name = st.selectbox("Worker / subcontractor", list(piece_workers.keys()))
                piece_date = st.date_input("Work date", datetime.now().date())
                piece_task = st.text_input("Specific task completed")
                piece_area = st.text_input("Work area")
                piece_quantity = st.number_input("Measured quantity", min_value=0.0, step=1.0)
                piece_unit = st.text_input("Unit", value="m²")
                piece_rate = st.number_input("Agreed rate per unit (KSh)", min_value=0.0, step=10.0)
                piece_verified_by = st.text_input("Verified by")
                piece_status = st.selectbox("Verification status", ["Pending", "Verified", "Rejected"])
                submit_piece = st.form_submit_button("Log piece-work", use_container_width=True)
            if submit_piece:
                piece_worker = piece_workers[piece_worker_name]
                result = api_post("/labor/piece-work", json={
                    "labor_id": piece_worker["id"], "project_id": piece_worker["project_id"],
                    "work_date": piece_date.isoformat(), "task_completed": piece_task.strip(),
                    "work_area": piece_area.strip() or None, "quantity": piece_quantity,
                    "unit": piece_unit.strip(), "unit_rate": piece_rate,
                    "verified_by": piece_verified_by.strip() or None, "status": piece_status,
                })
                if result:
                    st.success("Piece-work record saved.")
                    st.cache_data.clear()
            piece_rows = api_get("/labor/piece-work", params=params or None) or []
            if piece_rows:
                st.dataframe(pd.DataFrame([{
                    "Date": row.get("work_date"), "Worker": row.get("labor_id"),
                    "Task": row.get("task_completed"), "Quantity": f"{row.get('quantity', 0)} {row.get('unit', '')}",
                    "Amount": money(row.get("total_amount", 0)), "Status": row.get("status"),
                } for row in piece_rows]), use_container_width=True, hide_index=True)

    with tab_payroll:

        if not selected_project_id:
            st.info("Select one active project in the sidebar to prepare weekly payroll.")
        elif not labor:
            st.info("Add workers and record attendance before preparing payroll.")
        else:
            current_week_start = datetime.now().date() - timedelta(
                days=datetime.now().weekday()
            )
            period_start = st.date_input(
                "Week starting (Monday)",
                current_week_start,
                key="payroll_period_start",
            )
            period_end = period_start + timedelta(days=6)
            st.caption(f"Payroll period: {period_start:%b %d, %Y} to {period_end:%b %d, %Y}")

            preview = api_get(
                "/labor/payroll/preview",
                params={
                    "project_id": selected_project_id,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            ) or []

            if preview:
                preview_rows = [
                    {
                        "Worker / Crew": row.get("labor_name", "Unknown worker"),
                        "Days": row.get("days_worked", 0),
                        "Gross": money(row.get("gross_amount", 0)),
                        "Piece Work": money(row.get("piece_work_amount", 0)),
                        "Advances": money(row.get("advances", 0)),
                        "Net Payable": money(row.get("net_amount", 0)),
                    }
                    for row in preview
                ]
                st.dataframe(
                    pd.DataFrame(preview_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                if st.button("Generate Weekly Payroll", use_container_width=True):
                    generated = api_post(
                        "/labor/payroll",
                        json={
                            "project_id": selected_project_id,
                            "period_start": period_start.isoformat(),
                            "period_end": period_end.isoformat(),
                        },
                    )
                    if generated:
                        st.success("Weekly payroll generated as Draft. Review and approve it below.")
                        payroll_records = generated
                    else:
                        payroll_records = []
            else:
                st.info("No attendance or advances found for this week.")
                payroll_records = []

            if "payroll_records" not in locals():
                payroll_records = api_get(
                    "/labor/payroll",
                    params={
                        "project_id": selected_project_id,
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                    },
                ) or []

            if payroll_records:
                worker_names = {worker["id"]: worker["name"] for worker in labor}
                st.subheader("Payroll status")
                for payroll in payroll_records:
                    worker_name = worker_names.get(payroll.get("labor_id"), "Unknown worker")
                    with st.container(border=True):
                        st.write(
                            f"**{worker_name}** — {payroll.get('status', 'Draft')} — "
                            f"Net payable: **{money(payroll.get('net_amount', 0))}**"
                        )
                        st.caption(
                            f"{payroll.get('days_worked', 0)} days | "
                            f"Gross {money(payroll.get('gross_amount', 0))} | "
                            f"Advances {money(payroll.get('advances', 0))}"
                        )

                        if payroll.get("status") == "Draft":
                            approver = st.text_input(
                                "Approved by",
                                key=f"approver_{payroll['id']}",
                            )
                            if st.button(
                                "Approve Payroll",
                                key=f"approve_{payroll['id']}",
                            ):
                                approved = api_post(
                                    f"/labor/payroll/{payroll['id']}/approve",
                                    json={"approved_by": approver},
                                )
                                if approved:
                                    st.success(f"Payroll approved for {worker_name}.")
                                    st.cache_data.clear()
                                    st.rerun()

                        elif payroll.get("status") == "Approved":
                            pay_col1, pay_col2, pay_col3 = st.columns(3)
                            with pay_col1:
                                payment_method = st.selectbox(
                                    "Payment method",
                                    ["M-Pesa", "Bank", "Cash", "Other"],
                                    key=f"method_{payroll['id']}",
                                )
                            with pay_col2:
                                payment_reference = st.text_input(
                                    "Payment reference",
                                    key=f"reference_{payroll['id']}",
                                )
                            with pay_col3:
                                paid_by = st.text_input(
                                    "Paid by",
                                    key=f"paid_by_{payroll['id']}",
                                )
                            if st.button("Mark as Paid", key=f"pay_{payroll['id']}"):
                                paid = api_post(
                                    f"/labor/payroll/{payroll['id']}/pay",
                                    json={
                                        "payment_method": payment_method,
                                        "payment_reference": payment_reference,
                                        "paid_by": paid_by,
                                    },
                                )
                                if paid:
                                    st.success(f"Payroll paid for {worker_name}.")
                                    st.cache_data.clear()
                                    st.rerun()
                        else:
                            st.caption(
                                f"Paid via {payroll.get('payment_method', '—')} | "
                                f"Reference: {payroll.get('payment_reference', '—')} | "
                                f"Paid by: {payroll.get('paid_by', '—')}"
                            )


# =============================================================================
# SITE REPORTS
# =============================================================================

elif navigation == "📝 Site Reports":

    st.title("📝 Site Reports")

    params = {}

    if selected_project_id:
        params["project_id"] = selected_project_id

    reports = api_get(
        "/site-reports",
        params=params or None,
    ) or []

    tab_new, tab_history = st.tabs(
        [
            "➕ Daily Report",
            "📋 Report History",
        ]
    )

    with tab_new:

        if not projects:
            st.warning(
                "Create a project first."
            )

        else:

            with st.form("site_report_form"):

                project_name_selected = st.selectbox(
                    "Project",
                    [p["name"] for p in projects],
                )

                report_date = st.date_input(
                    "Report Date",
                    datetime.now(),
                )

                foreman = st.text_input(
                    "Foreman Name"
                )

                work_completed = st.text_area(
                    "Work Completed Today"
                )

                headcount = st.number_input(
                    "Workers on Site",
                    min_value=0,
                    value=0,
                )

                materials_consumed = st.text_area(
                    "Materials Consumed"
                )

                delays = st.text_area(
                    "Delays / Incidents / Issues"
                )

                photos = st.file_uploader(
                    "Site Photos",
                    type=[
                        "jpg",
                        "jpeg",
                        "png",
                    ],
                    accept_multiple_files=True,
                )

                submit = st.form_submit_button(
                    "Submit Daily Report",
                    use_container_width=True,
                )

                if submit:

                    photo_urls = []

                    for photo in photos or []:

                        upload = api_post(
                            "/uploads",
                            files={
                                "file": (
                                    photo.name,
                                    photo.getvalue(),
                                    photo.type,
                                )
                            },
                        )

                        if upload:
                            photo_urls.append(
                                upload.get("url")
                            )

                    result = api_post(
                        "/site-reports",
                        json={
                            "project_id": project_map(
                                projects
                            )[project_name_selected],
                            "report_date": report_date.isoformat(),
                            "foreman_name": foreman,
                            "work_completed": work_completed,
                            "headcount": headcount,
                            "materials_consumed": materials_consumed,
                            "delays_issues": delays,
                            "photo_urls": photo_urls,
                        },
                    )

                    if result:
                        st.success(
                            "Daily site report submitted."
                        )
                        st.cache_data.clear()

    with tab_history:

        if not reports:
            st.info(
                "No site reports submitted yet."
            )

        else:

            for report in reports:

                with st.expander(
                    f"{report.get('report_date', 'Unknown date')} "
                    f"— {report.get('foreman_name') or 'Unknown foreman'}"
                ):

                    st.write(
                        "**Work completed**"
                    )
                    st.write(
                        report.get(
                            "work_completed"
                        ) or "—"
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(
                            "**Workers on site**"
                        )
                        st.write(
                            report.get(
                                "headcount",
                                0,
                            )
                        )

                        st.write(
                            "**Materials consumed**"
                        )
                        st.write(
                            report.get(
                                "materials_consumed"
                            ) or "—"
                        )

                    with col2:
                        st.write(
                            "**Delays / Issues**"
                        )
                        st.write(
                            report.get(
                                "delays_issues"
                            ) or "None reported"
                        )

                    photo_urls = report.get(
                        "photo_urls"
                    ) or []

                    if photo_urls:
                        st.write("**Site Photos**")

                        for url in photo_urls:
                            st.image(
                                url,
                                width=250,
                            )


# =============================================================================
# AI ASSISTANT
# =============================================================================

elif navigation == "🤖 AI Assistant":

    st.title("🤖 Project AI Assistant")

    st.caption(
        "Your construction data assistant"
    )

    st.info(
        "Ask questions about your live projects, spending, stock, labour and site reports."
    )

    st.subheader("Questions this assistant will handle")

    examples = [
        "How much have we spent on materials this month?",
        "Which project is spending the most?",
        "What materials are running low?",
        "How much do I owe the labour team?",
        "Show me today's site activity.",
        "How much have we spent on the Runda project?",
        "Give me a summary of this project.",
    ]

    for example in examples:
        st.write(f"• {example}")

    st.markdown("---")

    if "messages" not in st.session_state:

        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hello. I'm your construction "
                    "business assistant. Ask me about "
                    "projects, money, materials, labour "
                    "or site reports."
                ),
            }
        ]

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):
            st.write(
                message["content"]
            )

    user_query = st.chat_input(
        "Ask about your construction business..."
    )

    if user_query:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_query,
            }
        )

        with st.chat_message("user"):
            st.write(user_query)

        response_data = api_post(
            "/ai/ask",
            json={
                "question": user_query,
                "project_id": selected_project_id,
            },
        )
        response = (
            response_data.get("answer")
            if response_data
            else "I could not get an answer right now. Check that DeepSeek is configured on the backend."
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        with st.chat_message("assistant"):
            st.write(response)
