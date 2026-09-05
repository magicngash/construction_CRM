import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Construction CRM", page_icon="???", layout="wide")

# LIVE RENDER BACKEND URL
BACKEND_URL = "https://construction-crm-zdqc.onrender.com"

st.title("??? Construction CRM Dashboard")

# --- SIDEBAR: ADD NEW PROJECT ---
st.sidebar.header("? Add New Project")
with st.sidebar.form("new_project_form", clear_on_submit=True):
    p_name = st.text_input("Project Name", placeholder="e.g. KAMAKIS FLATS")
    p_loc = st.text_input("Location", placeholder="e.g. Kamakis")
    p_budget = st.number_input("Budget (Ksh)", min_value=0.0, step=10000.0, value=350000.0)
    p_status = st.selectbox("Status", ["In Progress", "Planning", "Completed"])
    p_notes = st.text_area("Notes", placeholder="Optional details...")
    
    submit_btn = st.form_submit_button("Save Project")

if submit_btn:
    if p_name and p_loc:
        payload = {
            "name": p_name,
            "location": p_loc,
            "budget": p_budget,
            "status": p_status,
            "notes": p_notes
        }
        try:
            res = requests.post(f"{BACKEND_URL}/projects", json=payload)
            if res.status_code == 200:
                st.sidebar.success(f"Project '{p_name}' saved successfully!")
                st.rerun()
            else:
                st.sidebar.error(f"Failed to save project: {res.text}")
        except Exception as e:
            st.sidebar.error(f"Connection error: {e}")
    else:
        st.sidebar.warning("Please provide both a project name and location.")

# --- DASHBOARD METRICS & TABLE ---
try:
    response = requests.get(f"{BACKEND_URL}/projects")
    if response.status_code == 200:
        projects = response.json()
        
        if projects:
            df = pd.DataFrame(projects)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Projects", len(df))
            col2.metric("Total Budget", f"Ksh {df['budget'].sum():,.2f}")
            col3.metric("Active Projects", len(df[df['status'] == 'In Progress']))
            
            st.divider()
            
            st.subheader("Active Projects Overview")
            st.dataframe(
                df[["name", "location", "budget", "status", "created_at"]],
                use_container_width=True
            )
        else:
            st.info("No projects found in Supabase.")
    else:
        st.error(f"Failed to fetch data (Status Code: {response.status_code})")
except Exception as e:
    st.error(f"Backend request failed: {e}")
