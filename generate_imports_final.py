# generate_imports_final.py
import csv
import os
import re


def clean_name(name):
    """
    Cleans up a name by removing extra whitespace, brackets, specific phrases,
    and converting to a consistent case (Title Case). This must be identical
    to the cleaning function in discover.py for consistent results.
    """

    if not isinstance(name, str):
        return ''

    name = name.strip().title()
    name = re.sub(r'\(.*?\)', '', name)
    phrases_to_remove = ["Theory", "Practical", "Lab", "Class"]
    for phrase in phrases_to_remove:
        name = re.sub(phrase, '', name, flags=re.IGNORECASE)

    return " ".join(name.strip().split())


def generate_final_files():
    print("--- Generating Final, ID-Based Import Files ---")

    # --- Step 1: Load the master lists into Name-to-ID maps ---
    try:
        with open('teachers.csv', 'r', encoding='utf-8-sig') as f:
            teacher_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
        with open('subjects.csv', 'r', encoding='utf-8-sig') as f:
            subject_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
        with open('sections.csv', 'r', encoding='utf-8-sig') as f:
            section_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
    except FileNotFoundError as e:
        print(f"\nFATAL ERROR: A master file is missing: {e.filename}.")
        print("Please ensure teachers.csv, subjects.csv, and sections.csv exist before running.")
        return

    # --- Step 2: Read the user-provided input files ---
    try:
        with open('staging_data.csv', 'r', encoding='utf-8-sig') as f:
            staging_rows = list(csv.DictReader(f))
        with open('requirements_input.csv', 'r', encoding='utf-8-sig') as f:
            requirements_rows = list(csv.DictReader(f))
    except FileNotFoundError as e:
        print(f"\nFATAL ERROR: An input file is missing: {e.filename}.")
        print("Please ensure staging_data.csv and requirements_input.csv exist.")
        return

    # --- Step 3: Generate the final 'assignments.csv' with IDs ---
    assignments_with_ids = []
    print("\nProcessing staging_data.csv...")
    for row in staging_rows:
        teacher = clean_name(row.get('teacher_name', ''))
        subject = clean_name(row.get('subject_name', ''))
        section = clean_name(row.get('section_name', ''))

        if teacher in teacher_map and subject in subject_map and section in section_map:
            assignments_with_ids.append({
                'class_section_id': section_map[section],
                'subject_id': subject_map[subject],
                'teacher_id': teacher_map[teacher]
            })
        elif teacher:  # Only warn if there's a teacher assigned, otherwise it's just a subject listing
            print(f"  - WARNING: Skipping assignment row. A name was not found in master lists: {row}")

    with open('assignments.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'teacher_id'])
        writer.writeheader()
        writer.writerows(assignments_with_ids)
    print(f"-> Successfully created final 'assignments.csv' with {len(assignments_with_ids)} entries.")

    # --- Step 4: Generate the final 'requirements.csv' with IDs ---
    requirements_with_ids = []
    print("\nProcessing requirements_input.csv...")
    for row in requirements_rows:
        subject = clean_name(row.get('subject_name', ''))
        section = clean_name(row.get('section_name', ''))
        periods = int(row.get('periods_per_week', 0))

        if periods > 0 and subject in subject_map and section in section_map:
            requirements_with_ids.append({
                'class_section_id': section_map[section],
                'subject_id': subject_map[subject],
                'periods_per_week': periods
            })
        elif periods > 0:  # Only warn if periods are specified but a name is wrong
            print(f"  - WARNING: Skipping requirement row. A name was not found in master lists: {row}")

    # This OVERWRITES the old requirements.csv with the new, final, ID-based one
    with open('requirements.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'periods_per_week'])
        writer.writeheader()
        writer.writerows(requirements_with_ids)
    print(f"-> Successfully created final 'requirements.csv' with {len(requirements_with_ids)} entries.")

    print("\n--- All files are now ready for import_final.py ---")


if __name__ == '__main__':
    generate_final_files()