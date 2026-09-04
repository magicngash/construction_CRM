from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import supabase

app = FastAPI(title="Construction CRM API")

# --- CORS MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class ProjectCreate(BaseModel):
    name: str
    location: str
    budget: float
    status: str = "In Progress"
    notes: str = ""

# --- ROUTES ---
@app.get("/")
def read_root():
    return {"status": "online", "message": "Construction CRM API"}

@app.get("/projects")
def get_projects():
    try:
        response = supabase.table("projects").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/projects")
def create_project(project: ProjectCreate):
    try:
        response = supabase.table("projects").insert(project.dict()).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
