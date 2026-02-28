# process_staging_data.py (Version 6 - Reads Template)
import csv
import os
import re


# (The clean_name and load_master_list functions are unchanged)
def clean_name(name):
    if not isinstance(name, str): return ''
    name = name.strip().title()
    name = re.sub(r'\(.*?\)', '', name)
    phrases_to_remove = ["Theory", "Practical", "Lab", "Class"]
    for phrase in phrases_to_remove:
        name = re.sub(phrase, '', name, flags=re.IGNORECASE)
    return " ".join(name.strip().split())


def load_master_list(filename, name_col='name', id_col='id'):
    master_map = {}
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                clean_key = clean_name(row[name_col])
                if clean_key: master_map[clean_key] = row[name_col]
        print(f"-> Loaded master list from '{filename}'.")
    except FileNotFoundError:
        print(f"-> Master list '{filename}' not found.")
    return master_map


def process_staging_file():
    print("--- Processing Staging Data ---")

    # Steps 1-5: Discover entities and write base files (unchanged)
    master_teacher_map = load_master_list('teachers.csv')
    master_subject_map = load_master_list('subjects.csv')
    master_section_map = load_master_list('sections.csv')

    try:
        with open('staging_data.csv', 'r', encoding='utf-8-sig') as f:
            staging_rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print("ERROR: 'staging_data.csv' not found.");
        return

    all_teachers = set(master_teacher_map.keys())
    all_subjects = set(master_subject_map.keys())
    all_sections = set(master_section_map.keys())
    # ... (Discovery and warning logic is the same) ...
    for row in staging_rows:
        teacher = clean_name(row.get('teacher_name', ''))
        subject = clean_name(row.get('subject_name', ''))
        section = clean_name(row.get('section_name', ''))
        if teacher: all_teachers.add(teacher)
        if subject: all_subjects.add(subject)
        if section: all_sections.add(section)

    final_teachers = sorted(list(all_teachers))
    final_subjects = sorted(list(all_subjects))
    final_sections = sorted(list(all_sections))

    teacher_map = {name: i + 1 for i, name in enumerate(final_teachers)}
    subject_map = {name: i + 1 for i, name in enumerate(final_subjects)}
    section_map = {name: i + 1 for i, name in enumerate(final_sections)}

    with open('teachers.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f);
        writer.writerow(['id', 'name'])
        for name in final_teachers: writer.writerow([teacher_map[name], name])
    with open('subjects.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f);
        writer.writerow(['id', 'name', 'color'])
        for name in final_subjects: writer.writerow([subject_map[name], name, '#E0E0E0'])
    with open('sections.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f);
        writer.writerow(['id', 'name', 'periods_per_day'])
        for name in final_sections: writer.writerow([section_map[name], name, 8])

    assignments_with_ids = []
    requirements_template_pairs = set()

    for row in staging_rows:
        teacher_name = clean_name(row.get('teacher_name', ''))
        subject_name = clean_name(row.get('subject_name', ''))
        section_name = clean_name(row.get('section_name', ''))
        if teacher_name and subject_name and section_name:
            assignments_with_ids.append(
                {'class_section_id': section_map[section_name], 'subject_id': subject_map[subject_name],
                 'teacher_id': teacher_map[teacher_name]})
        if subject_name and section_name:
            requirements_template_pairs.add((section_name, subject_name))

    with open('assignments.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'teacher_id'])
        writer.writeheader();
        writer.writerows(assignments_with_ids)

    # --- STEP 6 (NEW LOGIC): Check for the template and generate the final requirements.csv ---
    template_filename = 'EDIT_THIS_REQUIREMENTS_TEMPLATE.csv'
    final_requirements_filename = 'requirements.csv'

    try:
        # Check if the user has filled out the template
        with open(template_filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # Check if there's any data and if periods have been filled in
            has_filled_periods = any(int(row.get('periods_per_week', 0)) > 0 for row in reader)

        if has_filled_periods:
            print(f"\n-> Found completed '{template_filename}'. Generating final '{final_requirements_filename}'...")
            requirements_with_ids = []
            # Re-open the file to read from the start
            with open(template_filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    section_name = row['section_name']
                    subject_name = row['subject_name']
                    periods = int(row.get('periods_per_week', 0))

                    if periods > 0 and section_name in section_map and subject_name in subject_map:
                        requirements_with_ids.append({
                            'class_section_id': section_map[section_name],
                            'subject_id': subject_map[subject_name],
                            'periods_per_week': periods
                        })

            with open(final_requirements_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'periods_per_week'])
                writer.writeheader();
                writer.writerows(requirements_with_ids)
            print(f"-> Successfully created '{final_requirements_filename}'.")
            print("\n--- All files ready! You can now run import_final.py. ---")

        else:  # Template exists but is empty
            raise FileNotFoundError  # Treat it as if it's not ready

    except (FileNotFoundError, StopIteration):
        # If the template doesn't exist or is empty, create it for the user
        print("\n-> Generating requirements template for you to fill in...")
        with open(template_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f);
            writer.writerow(['section_name', 'subject_name', 'periods_per_week'])
            for section, subject in sorted(list(requirements_template_pairs)):
                writer.writerow([section, subject, 0])
        print(f"-> Created '{template_filename}'.")
        print("\n--- ACTION REQUIRED ---")
        print(f"1. Open '{template_filename}' and fill in the periods_per_week.")
        print("2. Save the file.")
        print("3. Run this script (process_staging_data.py) again to generate the final requirements.csv.")


if __name__ == '__main__':
    process_staging_file()