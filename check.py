# check_my_db.py
import os
from sqlalchemy import create_engine, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def verify():
    print(f"--- DATABASE DIAGNOSTIC ---")
    print(f"1. Looking for database at: {os.path.abspath(DB_PATH)}")

    if not os.path.exists(DB_PATH):
        print("ERROR: File does not exist at that path!")
        return

    engine = create_engine(f'sqlite:///{DB_PATH}')

    with engine.connect() as conn:
        # Check Sections
        res = conn.execute(text("SELECT name FROM class_sections"))
        sections = [row[0] for row in res]
        print(f"2. Found {len(sections)} sections in DB: {sections}")

        # Check Requirements
        res = conn.execute(text("SELECT count(*) FROM subject_requirements"))
        req_count = res.scalar()
        print(f"3. Found {req_count} rows in Subject Requirements table.")


verify()