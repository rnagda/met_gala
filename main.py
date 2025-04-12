import asyncio
import os
import random
import sqlite3
import traceback

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from helper import authenticate_google_drive, authenticate_google_sheet, compareGPT, download_and_convert, parse_google_sheet
from dotenv import load_dotenv
from pillow_heif import register_heif_opener

load_dotenv()
app = FastAPI()
register_heif_opener()

# --- Database Setup ---

def get_db():
    conn = sqlite3.connect("teams.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            team_name TEXT,
            object_name TEXT,
            file_id TEXT,
            file_name TEXT, 
            points INTEGER,
            PRIMARY KEY(team_name, object_name, points)
            FOREIGN KEY(team_name) REFERENCES teams(name)
        )
    """)
    conn.commit()
    conn.close()

def initialize_teams():
    conn = sqlite3.connect("teams.db")
    cursor = conn.cursor()

    # Check if any teams already exist
    cursor.execute("SELECT COUNT(*) FROM teams")
    count = cursor.fetchone()[0]

    if count == 0:
        for i in range(1, 31):  # Team 1 to Team 30
            cursor.execute("INSERT INTO teams (name, score) VALUES (?, ?)", (f"Team {i}", 0))
        conn.commit()

    conn.close()

init_db()
initialize_teams()

# --- Models ---
class ScoreResponseInput(BaseModel):
    response_id: int
    points: int

class Adjustment(BaseModel):
    team: str
    adjustment: int

# --- Endpoints ---

@app.get("/standings")
def get_standings():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY score DESC").fetchall()
    conn.close()
    return teams

@app.get("/teams")
def get_standings():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY id ASC").fetchall()
    conn.close()
    return teams


@app.get("/reset_db_i_am_sure")
def get_standings():
    conn = get_db()
    conn.execute("DROP TABLE IF EXISTS teams")
    conn.execute("DROP TABLE IF EXISTS responses")
    conn.close()
    init_db()
    initialize_teams()
    return []


@app.get("/met_standings")
def standings_page():
    return FileResponse(os.path.join("frontend", "standings.html"))

@app.get("/umangs_secret_adjust")
def show_adjust_page():
    return FileResponse(os.path.join("frontend", "adjust.html"))


@app.post("/adjust")
def adjust_score(data: Adjustment):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE teams SET score = score + ? WHERE name = ?", (data.adjustment, data.team))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Team not found")
    conn.commit()
    conn.close()
    return {"message": "Score updated"}


async def poll_for_new_files():
    await asyncio.sleep(5)  # optional: short delay before first run
    drive_service = authenticate_google_drive()
    sheets_service = authenticate_google_sheet()

    while True:
        print('Polling')
        try:
            data = parse_google_sheet(sheets_service)
            conn = get_db()
            cursor = conn.cursor()
            for d in data:
                file_id = d[2].split("id=")[-1]
                team_name = d[1]
                file_name = drive_service.files().get(fileId=file_id, fields='name').execute()['name']
                object_type = d[3].split(':')[0].lstrip()
                object_name = d[3].split(':')[-1].lstrip()
                output_file_name = f'submissions/{file_name}'.replace('heic', 'jpg')
                cursor.execute("""SELECT 1 FROM responses WHERE team_name = ? AND object_name = ? AND points != 0""", (team_name, object_name))
                exists = cursor.fetchone() is not None
                print(exists)
                if not exists:
                    file_name = download_and_convert(drive_service, file_id, file_name)
                    match_found = False
                    if "yes" in compareGPT(file_name, f'correct_images/{object_name}.jpg').lower():
                        match_found = True
                    points = 0 if not match_found else 100 if object_type == 'Person' else 50 
                    cursor.execute("""INSERT INTO responses (team_name, file_id, file_name, points, object_name) VALUES (?, ?, ?, ?, ?)""", (team_name, file_id, file_name, points, object_name))
                    cursor.execute("UPDATE teams SET score = score + ? WHERE name = ?", (points, team_name))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error checking files: {traceback.print_exc()}")

        await asyncio.sleep(20)  # run every 20 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_for_new_files())

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
