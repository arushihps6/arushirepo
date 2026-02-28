# export_OLD_database.py
import csv
import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# --- IMPORTANT: We define the OLD database structure right here ---
# This avoids importing the NEW, updated models from main.py
Base = declarative_base()


class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String)


# --- This is the OLD ClassSection model, WITHOUT display_name ---
class ClassSection(Base):
    __tablename__ = 'class_sections'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    periods_per_day = Column(Integer)
    class_teacher_id = Column(Integer, ForeignKey('teachers.id'))


class TeacherAssignment(Base):
    __tablename__ = 'teacher_assignments'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    subject_id = Column(Integer, ForeignKey('subjects.id'))
    class_section_id = Column(Integer, ForeignKey('class_sections.id'))


class SubjectRequirement(Base):
    __tablename__ = 'subject_requirements'
    id = Column(Integer, primary_key=True)
    class_section_id = Column(Integer, ForeignKey('class_sections.id'))
    subject_id = Column(Integer, ForeignKey('subjects.id'))
    periods_per_week = Column(Integer)


# --- End of OLD model definitions ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_original_data():
    print("--- Exporting Original Database Data (Safe Mode) ---")

    # Check if the correct DB file is being used
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}. Please ensure your old, working database is here.")
        return

    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("Exporting base tables...")
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

        print("Exporting relationship tables...")
        with open('assignments.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['class_section_id', 'subject_id', 'teacher_id'])
            for a in session.query(TeacherAssignment).all(): writer.writerow(
                [a.class_section_id, a.subject_id, a.teacher_id])

        with open('requirements.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['class_section_id', 'subject_id', 'periods_per_week'])
            for r in session.query(SubjectRequirement).all(): writer.writerow(
                [r.class_section_id, r.subject_id, r.periods_per_week])

        print("\n--- Export Complete ---")
        print(
            "You now have clean CSVs of your old data. You can now manually add the 'display_name' column to sections.csv.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    export_original_data()