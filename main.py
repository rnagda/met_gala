from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import os
import random
import sqlite3

app = FastAPI()

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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            content TEXT,
            is_scored BOOLEAN DEFAULT FALSE,
            points INTEGER DEFAULT 0,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("""DELETE FROM teams""")
    conn.commit()
    conn.close()

def initialize_teams():
    conn = sqlite3.connect("teams.db")
    cursor = conn.cursor()

    # Check if any teams already exist
    cursor.execute("SELECT COUNT(*) FROM teams")
    count = cursor.fetchone()[0]

    if count == 0:
        for i in range(1, 26):  # Team 1 to Team 25
            cursor.execute("INSERT INTO teams (name, score) VALUES (?, ?)", (f"Team {i}", random.randrange(50, 2050, 50)))
        conn.commit()

    conn.close()

init_db()
initialize_teams()

# --- Models ---
class TeamScoreAdjust(BaseModel):
    team_id: int
    change: int

class ScoreResponseInput(BaseModel):
    response_id: int
    points: int

# --- Endpoints ---

@app.get("/standings_data")
def get_standings():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY score DESC").fetchall()
    conn.close()
    return [dict(team) for team in teams]


@app.get("/standings")
def standings_page():
    return FileResponse(os.path.join("frontend", "standings.html"))


@app.post("/adjust_score")
def adjust_score(data: TeamScoreAdjust):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE teams SET score = score + ? WHERE id = ?", (data.change, data.team_id))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Team not found")
    conn.commit()
    conn.close()
    return {"message": "Score updated"}

@app.get("/pending_responses")
def get_pending_responses():
    conn = get_db()
    responses = conn.execute("SELECT * FROM responses WHERE is_scored = 0").fetchall()
    conn.close()
    return [dict(response) for response in responses]

@app.post("/score_response")
def score_response(data: ScoreResponseInput):
    conn = get_db()
    cursor = conn.cursor()
    response = cursor.execute("SELECT * FROM responses WHERE id = ? AND is_scored = 0", (data.response_id,)).fetchone()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found or already scored")

    cursor.execute("UPDATE responses SET is_scored = 1, points = ? WHERE id = ?", (data.points, data.response_id))
    cursor.execute("UPDATE teams SET score = score + ? WHERE id = ?", (data.points, response["team_id"]))
    conn.commit()
    conn.close()
    return {"message": "Response scored and team updated"}


app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
