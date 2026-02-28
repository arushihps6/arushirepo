# import_debug_ids.py (Corrected)
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy import event


# This is a special command to allow inserting IDs in SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


from main import Base, Teacher, Subject, ClassSection, TeacherAssignment, SubjectRequirement

# --- FIX: ADDED MISSING PATH DEFINITIONS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


# -------------------------------------------

def import_raw_ids():
    print("--- Starting RAW ID Import ---")
    engine = create_engine(f'sqlite:///{DB_PATH}')

    # Recreate the database schema from scratch
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # --- IMPORTANT: Insert data while manually setting Primary Keys ---
        # This is a low-level operation to ensure a perfect copy

        with open('teachers_with_ids.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            session.bulk_insert_mappings(Teacher, [row for row in reader])

        with open('subjects_with_ids.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            session.bulk_insert_mappings(Subject, [row for row in reader])

        with open('sections_with_ids.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            session.bulk_insert_mappings(ClassSection, [row for row in reader])

        session.commit()
        print("-> Base entities (Teachers, Subjects, Sections) imported with original IDs.")

        # --- Now import the relationships using the preserved IDs ---

        with open('assignments_with_ids.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            session.bulk_insert_mappings(TeacherAssignment, [row for row in reader])

        with open('requirements_with_ids.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            session.bulk_insert_mappings(SubjectRequirement, [row for row in reader])

        session.commit()
        print("-> Relationships (Assignments, Requirements) imported with original IDs.")
        print("\n--- Raw ID Import Complete. The database should be an identical clone. ---")

    except Exception as e:
        print(f"\nAn error occurred during raw import: {e}");
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    import_raw_ids()