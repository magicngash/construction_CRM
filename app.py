import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Construction CRM", page_icon="???", layout="wide")

# BACKEND API CONFIGURATION
BACKEND_URL = "https://your-render-app.onrender.com"

st.title("??? Construction CRM Dashboard")

# Fetch projects from FastAPI
try:
    response = requests.get(f"{BACKEND_URL}/projects")
    if response.status_code == 200:
        projects = response.json()
        
        if projects:
            df = pd.DataFrame(projects)
            
            # --- METRICS OVERVIEW ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Projects", len(df))
            col2.metric("Total Budget", f"Ksh {df['budget'].sum():,.2f}")
            col3.metric("Active Projects", len(df[df['status'] == 'In Progress']))
            
            st.divider()
            
            # --- PROJECTS TABLE ---
            st.subheader("Active Projects Overview")
            st.dataframe(
                df[["name", "location", "budget", "status", "created_at"]],
                use_container_width=True
            )
        else:
            st.info("No projects found in the database.")
    else:
        st.error(f"Failed to fetch data from API (Status Code: {response.status_code})")
except Exception as e:
        st.error(f"Unable to connect to backend service: {e}")
