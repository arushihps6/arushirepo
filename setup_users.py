# setup_users.py (IDE-Friendly Version)
# import getpass  <-- We no longer need this
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import Base, Teacher, User

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")


def setup_teacher_logins():
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    existing_user_teacher_ids = {user.teacher_id for user in session.query(User).all()}
    teachers_without_users = session.query(Teacher).order_by(Teacher.name).all()

    teachers_to_process = [t for t in teachers_without_users if t.id not in existing_user_teacher_ids]

    if not teachers_to_process:
        print("All teachers already have user accounts.");
        session.close();
        return

    users_created_count = 0
    print("Found teachers without user accounts. Let's create them.")

    for teacher in teachers_to_process:
        print(f"\n--- Creating account for: {teacher.name} ---")

        username_prompt = f"  Enter username for {teacher.name} (or type 'quit' to exit, Enter to skip): "
        username = input(username_prompt).strip()

        if username.lower() == 'quit':
            print("\nExiting setup...");
            break

        if not username:
            print(f"  Skipping account creation for {teacher.name}.");
            continue

        while session.query(User).filter_by(username=username).first():
            print("  Username already exists. Please choose another.")
            username = input(f"  Enter a different username for {teacher.name} (or 'quit' to exit): ").strip()
            if username.lower() == 'quit': break
            if not username: break

        if username.lower() == 'quit':
            print("\nExiting setup...");
            break

        if not username:
            print(f"  Skipping account creation for {teacher.name}.");
            continue

        # --- MODIFICATION: Replaced getpass with regular input() ---
        # WARNING: Password will be visible as you type.
        password = input(f"  Enter password for {username}: ")

        if not password:
            confirm = input("  Password is empty. Is this correct? (y/n): ").lower()
            if confirm != 'y':
                print(f"  Account creation for {username} cancelled.");
                continue

        new_user = User(username=username, password=password, teacher_id=teacher.id)
        session.add(new_user)
        users_created_count += 1
        print(f"  Account for {username} queued for creation.")

    if users_created_count > 0:
        session.commit()
        print(f"\n{users_created_count} new user account(s) have been saved.")
    else:
        print("\nNo new user accounts were created.")

    session.close()


if __name__ == '__main__':
    setup_teacher_logins()