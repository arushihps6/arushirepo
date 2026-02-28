# view_users.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import your models
from main import Base, User, Teacher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def show_all_users():
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- Listing All User Accounts in the Database ---")

    # Query all users and join with the Teacher table to get the name
    users = session.query(User).join(Teacher).order_by(Teacher.name).all()

    if not users:
        print("No user accounts found.")
    else:
        # Define column widths for neat printing
        # Find the longest username and teacher name to format the table nicely
        max_user = max(len(u.username) for u in users) if users else 8
        max_name = max(len(u.teacher.name) for u in users) if users else 12

        # Header
        print(f"{'Username':<{max_user}} | {'Password':<15} | {'Linked Teacher':<{max_name}}")
        print(f"{'-' * max_user}-+-{'-' * 15}-+-{'-' * max_name}")

        # Rows
        for user in users:
            print(f"{user.username:<{max_user}} | {user.password:<15} | {user.teacher.name:<{max_name}}")

    session.close()


if __name__ == '__main__':
    show_all_users()