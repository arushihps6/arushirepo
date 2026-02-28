# export_assignments_names.py (THE ULTIMATE FIX)
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text  # <--- CRITICAL NEW IMPORT

# We still need to import the models for the table names
from main import Base, Teacher, Subject, ClassSection, TeacherAssignment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_name_assignments():
    print("--- Exporting ALL Assignments by NAME for Editing (Pure SQL) ---")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # --- THE FINAL FIX: Wrap the SQL string with text() ---
        sql_query = text("""
        SELECT 
            T.name AS teacher_name,
            S.name AS subject_name,
            CS.name AS section_name
        FROM teacher_assignments AS TA
        JOIN teachers AS T ON TA.teacher_id = T.id
        JOIN subjects AS S ON TA.subject_id = S.id
        JOIN class_sections AS CS ON TA.class_section_id = CS.id
        ORDER BY section_name, subject_name
        """)

        # Execute the raw SQL query
        result = session.execute(sql_query)

        assignments_by_name = []
        for row in result:
            assignments_by_name.append({
                'section_name': row.section_name,
                'subject_name': row.subject_name,
                'teacher_name': row.teacher_name
            })

        with open('OLD_ASSIGNMENTS_NAMES.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['section_name', 'subject_name', 'teacher_name'])
            writer.writeheader()
            writer.writerows(assignments_by_name)

        print("-> Successfully created 'OLD_ASSIGNMENTS_NAMES.csv'.")
        print("Please manually merge your new 11th/12th grade assignments into this file.")

    except Exception as e:
        print(f"\nERROR: Could not export old assignments: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    export_name_assignments()