# debug_assignments.py
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# IMPORTANT: We import the models from your main application
from main import Base, Teacher, Subject, ClassSection, TeacherAssignment

def inspect_database(db_path):
    """
    Connects to a database and prints a sorted, human-readable list of
    all teacher-subject-class assignments.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    print(f"\n--- Inspecting Assignments in: {os.path.basename(db_path)} ---")

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # This query joins all the tables to translate the IDs back into names
        assignments = session.query(
            ClassSection.name,
            Subject.name,
            Teacher.name
        ).join(
            TeacherAssignment, ClassSection.id == TeacherAssignment.class_section_id
        ).join(
            Subject, Subject.id == TeacherAssignment.subject_id
        ).join(
            Teacher, Teacher.id == TeacherAssignment.teacher_id
        ).order_by(
            ClassSection.name, Subject.name, Teacher.name  # Sort for consistent comparison
        ).all()

        if not assignments:
            print("  No assignments found in this database.")
        else:
            print(f"  Found {len(assignments)} total assignments.")
            for section_name, subject_name, teacher_name in assignments:
                # Print in a clean, consistent format
                print(f"  - Section: {section_name:<10} | Subject: {subject_name:<15} | Teacher: {teacher_name}")

    except Exception as e:
        print(f"An error occurred during inspection: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    # Check if a database file was provided as an argument
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
        inspect_database(db_file)
    else:
        print("Usage: python debug_assignments.py <path_to_database_file>")
        print("Example: python debug_assignments.py timetable_v5.db")