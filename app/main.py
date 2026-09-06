from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os

from app.api.endpoints import router as api_router
from app.database.loader import initialize_database
from app.config import settings

app = FastAPI(title="E-Commerce Analytics Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_dashboard_db():
    os.makedirs(os.path.dirname(settings.dashboard_db_path), exist_ok=True)
    conn = sqlite3.connect(settings.dashboard_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dashboard (
            id TEXT PRIMARY KEY,
            user_query TEXT,
            chart_config TEXT,
            raw_data TEXT,
            tool_calls TEXT,
            insight TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

@app.on_event("startup")
async def startup_event():
    print("Initializing databases...")
    initialize_database()
    init_dashboard_db()
    print("Startup complete.")

app.include_router(api_router, prefix="/api")

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
