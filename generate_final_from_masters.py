# generate_final_from_masters.py (V3 - Includes Sets)
import csv
import os
import re


def clean_name(name, is_subject=False):
    if not isinstance(name, str): return ''
    name = name.strip()
    if is_subject:
        # FIX: Preserve the (Sci) tag, but clean other brackets
        if "(Sci)" not in name:
            name = re.sub(r'\(.*?\)', '', name)

        phrases_to_remove = ["Theory", "Practical", "Lab", "Class", "Visual And Performing Arts"]
        for phrase in phrases_to_remove:
            name = re.sub(phrase, '', name, flags=re.IGNORECASE)
    return " ".join(name.split()).title()


def generate_final_files():
    print("--- Generating Final ID-Based Files (Including Sets) ---")

    try:
        with open('teachers.csv', 'r', encoding='utf-8-sig') as f:
            teacher_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
        with open('subjects.csv', 'r', encoding='utf-8-sig') as f:
            subject_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
        with open('sections.csv', 'r', encoding='utf-8-sig') as f:
            section_map = {clean_name(row['name']): row['id'] for row in csv.DictReader(f)}
    except FileNotFoundError as e:
        print(f"FATAL ERROR: Master file missing: {e.filename}");
        return

    # 1. Process Assignments
    if os.path.exists('assignments_input.csv'):
        assignments_with_ids = []
        with open('assignments_input.csv', 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                t, s, sec = clean_name(row.get('teacher_name')), clean_name(row.get('subject_name'), True), clean_name(
                    row.get('section_name'))
                if t in teacher_map and s in subject_map and sec in section_map:
                    assignments_with_ids.append({'class_section_id': section_map[sec], 'subject_id': subject_map[s],
                                                 'teacher_id': teacher_map[t]})
        with open('assignments.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'teacher_id'])
            writer.writeheader();
            writer.writerows(assignments_with_ids)
        print(f"-> assignments.csv created ({len(assignments_with_ids)} rows).")

    # 2. Process Requirements
    if os.path.exists('requirements_input.csv'):
        reqs_with_ids = []
        with open('requirements_input.csv', 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                s, sec = clean_name(row.get('subject_name'), True), clean_name(row.get('section_name'))
                p = int(row.get('periods_per_week', 0))
                if p > 0 and s in subject_map and sec in section_map:
                    reqs_with_ids.append(
                        {'class_section_id': section_map[sec], 'subject_id': subject_map[s], 'periods_per_week': p})
        with open('requirements.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['class_section_id', 'subject_id', 'periods_per_week'])
            writer.writeheader();
            writer.writerows(reqs_with_ids)
        print(f"-> requirements.csv created ({len(reqs_with_ids)} rows).")

    # 3. NEW: Process Concurrent Sets
    if os.path.exists('sets_input.csv'):
        sets_main = []
        set_sections = []
        set_subjects = []
        with open('sets_input.csv', 'r', encoding='utf-8-sig') as f:
            for i, row in enumerate(csv.DictReader(f), 1):
                set_id = i
                sets_main.append({'id': set_id, 'name': row['set_name'], 'color': row['color']})

                for s_name in row['section_names'].split(';'):
                    s_name = clean_name(s_name)
                    if s_name in section_map:
                        set_sections.append({'set_id': set_id, 'section_id': section_map[s_name]})

                for sub_name in row['subject_names'].split(';'):
                    sub_name = clean_name(sub_name, True)
                    if sub_name in subject_map:
                        set_subjects.append({'set_id': set_id, 'subject_id': subject_map[sub_name]})

        with open('concurrent_sets.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name', 'color'])
            writer.writeheader();
            writer.writerows(sets_main)
        with open('concurrent_set_sections.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['set_id', 'section_id'])
            writer.writeheader();
            writer.writerows(set_sections)
        with open('concurrent_set_subjects.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['set_id', 'subject_id'])
            writer.writeheader();
            writer.writerows(set_subjects)
        print(f"-> Set files created ({len(sets_main)} sets).")


if __name__ == '__main__':
    generate_final_files()