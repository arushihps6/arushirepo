# import_final.py (Hardened Version)
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, Teacher, Subject, ClassSection, TeacherAssignment, SubjectRequirement, ConcurrentSet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def clean_csv_dict(reader):
    """Removes stray whitespace/tabs and filters out empty rows."""
    cleaned_list = []
    for row in reader:
        # Clean whitespace from all keys and values
        clean_row = {str(k).strip(): str(v).strip() for k, v in row.items() if k is not None}
        # Only keep the row if it actually has an ID and isn't just a stray tab/space
        if clean_row.get('id') and clean_row['id'].isdigit():
            cleaned_list.append(clean_row)
        elif clean_row.get('class_section_id') and clean_row['class_section_id'].isdigit():
            # This handles the relationship tables (assignments/requirements)
            cleaned_list.append(clean_row)
    return cleaned_list


def import_final():
    print("--- Starting Final Database Import (Hardened) ---")
    engine = create_engine(f'sqlite:///{DB_PATH}')

    confirm = input("WARNING: This will DELETE all existing data. Proceed? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Import cancelled.");
        return

    print("Wiping old database...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("\n--- Step 1: Importing base entities... ---")

        files_and_models = [
            ('teachers.csv', Teacher),
            ('subjects.csv', Subject),
            ('sections.csv', ClassSection),
            ('concurrent_sets.csv', ConcurrentSet),
            ('assignments.csv', TeacherAssignment),
            ('requirements.csv', SubjectRequirement)
        ]

        for filename, Model in files_and_models:
            if not os.path.exists(filename):
                if filename == 'concurrent_sets.csv': continue
                print(f"FATAL ERROR: {filename} missing.")
                return

            with open(filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                data = clean_csv_dict(reader)
                if data:
                    session.bulk_insert_mappings(Model, data)
                    print(f"-> {filename} imported ({len(data)} rows).")

        session.commit()

        print("\n--- Step 2: Rebuilding relationships... ---")
        rel_files = [
            ('concurrent_set_sections.csv', 'concurrent_set_section'),
            ('concurrent_set_subjects.csv', 'concurrent_set_subject')
        ]

        for filename, table_name in rel_files:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8-sig') as f:
                    reader = list(csv.DictReader(f))
                    if reader:
                        session.execute(Base.metadata.tables[table_name].insert(), reader)
                        print(f"-> {filename} rebuilt.")

        session.commit()
        print("\n--- Import Complete! Database is ready. ---")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    import_final()