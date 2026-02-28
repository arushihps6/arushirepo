# export_debug_ids.py
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import Base, Teacher, Subject, ClassSection, TeacherAssignment, SubjectRequirement, ConcurrentSet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_raw_ids():
    print("--- Starting RAW ID Export ---")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Export base tables WITH their IDs
        with open('teachers_with_ids.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name'])
            for t in session.query(Teacher).all(): writer.writerow([t.id, t.name])

        with open('subjects_with_ids.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name', 'color'])
            for s in session.query(Subject).all(): writer.writerow([s.id, s.name, s.color])

        with open('sections_with_ids.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name', 'periods_per_day'])
            for s in session.query(ClassSection).all(): writer.writerow([s.id, s.name, s.periods_per_day])

        # Export relationship tables using ONLY IDs
        with open('assignments_with_ids.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['section_id', 'subject_id', 'teacher_id'])
            for a in session.query(TeacherAssignment).all(): writer.writerow(
                [a.class_section_id, a.subject_id, a.teacher_id])

        with open('requirements_with_ids.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['section_id', 'subject_id', 'periods_per_week'])
            for r in session.query(SubjectRequirement).all(): writer.writerow(
                [r.class_section_id, r.subject_id, r.periods_per_week])

        print("-> Raw ID export complete.")
    finally:
        session.close()


if __name__ == '__main__':
    export_raw_ids()