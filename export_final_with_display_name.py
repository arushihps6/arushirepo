# export_original_data.py
import csv, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, Teacher, Subject, ClassSection, TeacherAssignment, SubjectRequirement, ConcurrentSet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_original():
    print("--- Exporting Original Database Data (AS-IS) ---")
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Export all tables exactly as they are in the old database
        with open('teachers.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name'])
            for t in session.query(Teacher).order_by(Teacher.id).all(): writer.writerow([t.id, t.name])

        with open('subjects.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name', 'color'])
            for s in session.query(Subject).order_by(Subject.id).all(): writer.writerow([s.id, s.name, s.color])

        with open('sections.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['id', 'name', 'periods_per_day'])
            for s in session.query(ClassSection).order_by(ClassSection.id).all(): writer.writerow(
                [s.id, s.name, s.periods_per_day])

        # ... (rest of the export for assignments, requirements, etc. is the same)
        # Make sure this part is also in your script
        with open('assignments.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['class_section_id', 'subject_id', 'teacher_id'])
            for a in session.query(TeacherAssignment).order_by(TeacherAssignment.id).all(): writer.writerow(
                [a.class_section_id, a.subject_id, a.teacher_id])
        with open('requirements.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['class_section_id', 'subject_id', 'periods_per_week'])
            for r in session.query(SubjectRequirement).order_by(SubjectRequirement.id).all(): writer.writerow(
                [r.class_section_id, r.subject_id, r.periods_per_week])
        print("Export complete.")

    finally:
        session.close()


if __name__ == '__main__':
    export_original()