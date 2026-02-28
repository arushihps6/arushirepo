# export_sets_to_names.py
import csv
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, ConcurrentSet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def export_sets():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    sets = session.query(ConcurrentSet).all()
    if not sets:
        print("No concurrent sets found in the UI to export.")
        return

    with open('sets_input.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['set_name', 'color', 'section_names', 'subject_names'])
        for cset in sets:
            sec_names = ";".join([s.name for s in cset.sections])
            sub_names = ";".join([s.name for s in cset.subjects])
            writer.writerow([cset.name, cset.color, sec_names, sub_names])

    print("Success! Your UI sets are now saved in 'sets_input.csv'.")
    session.close()


if __name__ == '__main__':
    export_sets()