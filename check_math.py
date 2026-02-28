import csv
from collections import defaultdict

def check():
    # 1. Check Section Totals
    section_totals = defaultdict(int)
    with open('requirements_input.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            section_totals[row['section_name']] += int(row['periods_per_week'])

    print("--- Checking Class Totals ---")
    for sec, total in section_totals.items():
        limit = 30 if '11' in sec or '12' in sec else 40
        if total != limit:
            print(f"❌ ERROR: {sec} has {total} periods (Should be {limit})")

    # 2. Check Teacher Loads (Human Level)
    teacher_assignments = []
    with open('assignments_input.csv', 'r', encoding='utf-8-sig') as f:
        teacher_assignments = list(csv.DictReader(f))

    # Link periods to assignments
    req_map = {}
    with open('requirements_input.csv', 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            req_map[(row['section_name'], row['subject_name'])] = int(row['periods_per_week'])

    human_loads = defaultdict(int)
    for row in teacher_assignments:
        periods = req_map.get((row['section_name'], row['subject_name']), 0)
        # Group by Human Name (Strip the (2), (3) etc)
        base_name = row['teacher_name'].split(' (')[0].strip()
        human_loads[base_name] += periods

    print("\n--- Checking Human Teacher Loads ---")
    for name, load in human_loads.items():
        # A human cannot teach more than 40 periods in a 40-slot week
        # or more than 30 periods if they only teach seniors.
        # To be safe, we use 40 as the absolute physical limit.
        if load > 40:
            print(f"❌ FATAL: {name} is assigned {load} periods. This is physically impossible in one week.")

if __name__ == '__main__':
    check()