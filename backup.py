# extract_backup.py
import csv
import os
from sqlalchemy import create_engine, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def extract():
    engine = create_engine(f'sqlite:///{DB_PATH}')
    with engine.connect() as conn:
        print("--- Extracting Backup Data ---")

        # 1. Assignments
        sql_a = text("""
            SELECT CS.name as section_name, S.name as subject_name, T.name as teacher_name 
            FROM teacher_assignments TA 
            JOIN class_sections CS ON TA.class_section_id = CS.id 
            JOIN subjects S ON TA.subject_id = S.id 
            JOIN teachers T ON TA.teacher_id = T.id
        """)
        res_a = conn.execute(sql_a)
        with open('BACKUP_ASSIGNMENTS.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['section_name', 'subject_name', 'teacher_name'])
            writer.writeheader()
            writer.writerows([dict(row._mapping) for row in res_a])

        # 2. Requirements
        sql_r = text("""
            SELECT CS.name as section_name, S.name as subject_name, SR.periods_per_week 
            FROM subject_requirements SR 
            JOIN class_sections CS ON SR.class_section_id = CS.id 
            JOIN subjects S ON SR.subject_id = S.id
        """)
        res_r = conn.execute(sql_r)
        with open('BACKUP_REQUIREMENTS.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['section_name', 'subject_name', 'periods_per_week'])
            writer.writeheader()
            writer.writerows([dict(row._mapping) for row in res_r])

    print("Success! Created 'BACKUP_ASSIGNMENTS.csv' and 'BACKUP_REQUIREMENTS.csv'.")


extract()