# discover.py (Version 3 - Master List Discovery)
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


def discover_new_entities():
    print("--- Discovery Tool (v3) ---")

    # Files we are checking against
    master_files = {
        'teachers': 'teachers.csv',
        'subjects': 'subjects.csv',
        'sections': 'sections.csv'
    }

    # The file containing your new data
    input_file = 'assignments_input.csv'

    # Load master lists
    masters = {'teachers': set(), 'subjects': set(), 'sections': set()}
    for key, filename in master_files.items():
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8-sig') as f:
                # Sections uses 'display_name' sometimes, but we check against 'name'
                masters[key] = {clean_name(row['name'], is_subject=(key == 'subjects')) for row in csv.DictReader(f)}

    # Read the input assignments file
    if not os.path.exists(input_file):
        print(f"\nERROR: '{input_file}' not found. Please ensure your assignments are in this file.")
        return

    found_in_input = {'teachers': set(), 'subjects': set(), 'sections': set()}

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sec = clean_name(row.get('section_name', ''))
            sub = clean_name(row.get('subject_name', ''), is_subject=True)
            tea = clean_name(row.get('teacher_name', ''))

            if sec: found_in_input['sections'].add(sec)
            if sub: found_in_input['subjects'].add(sub)
            if tea: found_in_input['teachers'].add(tea)

    # Find what's missing from masters
    missing = {
        'teachers': found_in_input['teachers'] - masters['teachers'],
        'subjects': found_in_input['subjects'] - masters['subjects'],
        'sections': found_in_input['sections'] - masters['sections']
    }

    print("\n--- Discovery Report ---")
    all_clear = True

    for category in ['teachers', 'subjects', 'sections']:
        if missing[category]:
            all_clear = False
            print(f"\nNew {category.capitalize()} Found (Add these to {master_files[category]}):")
            for item in sorted(list(missing[category])):
                print(f"  - {item}")

    if all_clear:
        print("✅ All data in assignments_input.csv matches your master files!")
        print("You are ready to run 'generate_imports_final.py'.")
    else:
        print("\n--- ACTION REQUIRED ---")
        print("1. Open your master CSV files (teachers.csv, etc.)")
        print("2. Add the names listed above to the bottom of the files.")
        print("3. Assign them new, unique ID numbers.")
        print("4. Save the files and run this script again to verify.")


if __name__ == '__main__':
    discover_new_entities()