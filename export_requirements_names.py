# export_requirements_names.py
import csv
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_requirements():
    print("--- Extracting Old Requirements by Name ---")
    if not os.path.exists(DB_PATH):
        print("ERROR: Good database not found.")
        return

    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Use Pure SQL to avoid the display_name column crash
        sql = text("""
            SELECT CS.name as section_name, S.name as subject_name, SR.periods_per_week 
            FROM subject_requirements SR
            JOIN class_sections CS ON SR.class_section_id = CS.id
            JOIN subjects S ON SR.subject_id = S.id
        """)

        result = session.execute(sql)

        with open('OLD_REQUIREMENTS_NAMES.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['section_name', 'subject_name', 'periods_per_week'])
            writer.writeheader()
            for row in result:
                writer.writerow({
                    'section_name': row.section_name,
                    'subject_name': row.subject_name,
                    'periods_per_week': row.periods_per_week
                })
        print("-> Created 'OLD_REQUIREMENTS_NAMES.csv'.")
    finally:
        session.close()


if __name__ == '__main__':
    export_requirements()