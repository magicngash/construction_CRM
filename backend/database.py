import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mgguxpmjoluknqbicjxy.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY environment variable is not set. "
        "Get it from Project Settings > API > service_role key in the Supabase dashboard "
        "(this project: mgguxpmjoluknqbicjxy) and set it before starting the backend. "
        "This key bypasses RLS, so keep it server-side only — never in the Streamlit frontend."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)