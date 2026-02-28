# server.py (Corrected for DetachedInstanceError)
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload  # <-- IMPORT joinedload

import uvicorn
from main import Base, Teacher, Subject, ClassSection, ScheduleEntry, User

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")

# --- Database Setup ---
engine = create_engine(f'sqlite:///{DB_PATH}', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FastAPI App ---
app = FastAPI()


# --- API Models ---
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    teacher_id: int
    teacher_name: str


class TimetableEntry(BaseModel):
    day: str
    period: int
    subject_name: str
    section_name: str


# --- API Endpoints ---
@app.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    db = SessionLocal()

    # --- FIX: Use joinedload to EAGERLY load the related teacher ---
    user = (
        db.query(User)
        .options(joinedload(User.teacher))  # This tells SQLAlchemy to fetch the teacher info in the same query
        .filter(User.username == request.username)
        .first()
    )
    # --- END FIX ---

    # We can now safely close the session because all needed data is loaded
    db.close()

    if not user or user.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # This will now work because user.teacher is already loaded
    return LoginResponse(
        message="Login successful",
        teacher_id=user.teacher_id,
        teacher_name=user.teacher.name
    )


@app.get("/timetable/{teacher_id}", response_model=list[TimetableEntry])
def get_timetable(teacher_id: int):
    db = SessionLocal()
    # Eagerly load related objects to avoid N+1 query problems and detachment errors
    schedule = (
        db.query(ScheduleEntry)
        .options(
            joinedload(ScheduleEntry.subject),
            joinedload(ScheduleEntry.class_section)
        )
        .filter(ScheduleEntry.teacher_id == teacher_id)
        .all()
    )
    db.close()

    timetable_data = []
    for entry in schedule:
        if entry.subject and entry.class_section:
            timetable_data.append(TimetableEntry(
                day=entry.day,
                period=entry.period,
                subject_name=entry.subject.name,
                section_name=entry.class_section.name
            ))
    return timetable_data


# --- Main entry point to run the server ---
if __name__ == "__main__":
    print("Starting server...")
    print(f"Your database is located at: {DB_PATH}")
    # reload=True is great for development, it auto-restarts the server when you save changes
    # The corrected line in server.py
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)