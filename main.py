import sys
import os
import json
from collections import defaultdict
import random
import time
import traceback

from PySide6.QtCore import Qt, QSize, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QGroupBox, QSpinBox, QFormLayout, QListWidget, QListWidgetItem, QInputDialog,
    QMessageBox, QFileDialog, QHeaderView, QComboBox, QDialog, QDialogButtonBox, QScrollArea, QGridLayout,
    QLabel, QTableWidget, QTableWidgetItem, QCheckBox, QSplitter, QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QLineEdit, QTabWidget, QTextEdit
)
from PySide6.QtGui import QFont, QColor, QIcon, QMovie, QPixmap

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("Error: The 'ortools' library is required. Please install it using: pip install ortools")
    sys.exit(1)

try:
    from reportlab.platypus import SimpleDocTemplate, Table as ReportLabTable, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import landscape, A1
except ImportError:
    print("Error: The 'reportlab' library is required. Please install it using: pip install reportlab")
    sys.exit(1)

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

Base = declarative_base()


# region: ================= DATABASE MODELS =================
class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    schedule_entries = relationship("ScheduleEntry", back_populates="teacher", cascade="all, delete")
    class_teacher_of_section = relationship("ClassSection", back_populates="class_teacher", uselist=False)


class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#E0E0E0")
    assignments = relationship("TeacherAssignment", back_populates="subject", cascade="all, delete-orphan")
    requirements = relationship("SubjectRequirement", back_populates="subject", cascade="all, delete-orphan")
    schedule_entries = relationship("ScheduleEntry", back_populates="subject", cascade="all, delete")


class ClassSection(Base):
    __tablename__ = 'class_sections'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    # This is the new column
    display_name = Column(String)

    periods_per_day = Column(Integer, default=8)
    assignments = relationship("TeacherAssignment", back_populates="class_section", cascade="all, delete-orphan")
    schedule_entries = relationship("ScheduleEntry", back_populates="class_section", cascade="all, delete-orphan")
    requirements = relationship("SubjectRequirement", back_populates="class_section", cascade="all, delete-orphan")
    class_teacher_id = Column(Integer, ForeignKey('teachers.id'), unique=True, nullable=True)
    class_teacher = relationship("Teacher", back_populates="class_teacher_of_section")

class TeacherAssignment(Base):
    __tablename__ = 'teacher_assignments'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    class_section_id = Column(Integer, ForeignKey('class_sections.id'), nullable=False)
    teacher = relationship("Teacher", back_populates="assignments")
    subject = relationship("Subject", back_populates="assignments")
    class_section = relationship("ClassSection", back_populates="assignments")
    __table_args__ = (
        UniqueConstraint('subject_id', 'class_section_id', name='_subject_class_teacher_uc'),
    )


class ScheduleEntry(Base):
    __tablename__ = 'schedule_entries'
    id = Column(Integer, primary_key=True)
    class_section_id = Column(Integer, ForeignKey('class_sections.id', ondelete="CASCADE"), nullable=False)
    day = Column(String, nullable=False)
    period = Column(Integer, nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id', ondelete="CASCADE"))
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete="CASCADE"))
    class_section = relationship("ClassSection", back_populates="schedule_entries")
    subject = relationship("Subject", back_populates="schedule_entries")
    teacher = relationship("Teacher", back_populates="schedule_entries")
    __table_args__ = (
        UniqueConstraint('class_section_id', 'day', 'period', name='_class_day_period_uc'),
    )


class SubjectRequirement(Base):
    __tablename__ = 'subject_requirements'
    id = Column(Integer, primary_key=True)
    class_section_id = Column(Integer, ForeignKey('class_sections.id', ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id', ondelete="CASCADE"), nullable=False)
    periods_per_week = Column(Integer, nullable=False)
    class_section = relationship("ClassSection", back_populates="requirements")
    subject = relationship("Subject", back_populates="requirements")


concurrent_set_section = Table('concurrent_set_section', Base.metadata,
                               Column('set_id', Integer, ForeignKey('concurrent_sets.id', ondelete="CASCADE")),
                               Column('section_id', Integer, ForeignKey('class_sections.id', ondelete="CASCADE")))
concurrent_set_subject = Table('concurrent_set_subject', Base.metadata,
                               Column('set_id', Integer, ForeignKey('concurrent_sets.id', ondelete="CASCADE")),
                               Column('subject_id', Integer, ForeignKey('subjects.id', ondelete="CASCADE")))


class ConcurrentSet(Base):
    __tablename__ = 'concurrent_sets'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#FFCCCB")
    sections = relationship("ClassSection", secondary=concurrent_set_section)
    subjects = relationship("Subject", secondary=concurrent_set_subject)


from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # In a real app, this would be hashed!
    teacher_id = Column(Integer, ForeignKey('teachers.id'), unique=True, nullable=False)

    teacher = relationship("Teacher")

# endregion

# region: ================= SOLVER & WORKER THREAD =================
class SolverWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, solver_instance):
        super().__init__()
        self.solver = solver_instance

    def run(self):
        try:
            self.finished.emit(self.solver.solve())
        except Exception:
            self.error.emit(f"An error occurred in the solver thread:\n\n{traceback.format_exc()}")


class TimetableSolver:
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    def __init__(self, session):
        self.session = session
        self.model = cp_model.CpModel()
        self.all_sections = {s.id: s for s in self.session.query(ClassSection).all()}
        self.all_teachers = {t.id: t for t in self.session.query(Teacher).all()}
        self.concurrent_sets = self.session.query(ConcurrentSet).all()
        self.assignment_map = self._load_assignments()
        self.class_periods = {}
        self.subject_class_vars = defaultdict(list)

    def _load_assignments(self):
        return {(a.class_section_id, a.subject_id): a.teacher_id for a in self.session.query(TeacherAssignment).all()}

    def solve(self):
        print("\n--- Starting Timetable Generation (Diagnostic Mode) ---")
        start_time = time.time()

        # Run pre-check before even trying to solve
        errors = self.run_diagnostics()
        if errors:
            print("Step 1: Found data errors. Aborting.")
            # We return the errors as a string so the UI can show them
            return {"errors": errors}

        self._define_variables_and_constraints()
        print("Step 2: Model defined.")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(self.model)
        duration = time.time() - start_time

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Step 3: Solution found in {duration:.2f}s.")
            return self._extract_solution(solver)
        else:
            # If the solver fails, run a deep scan to find out why
            print("Step 4: No solution. Running Deep Diagnostics...")
            deep_errors = self.run_diagnostics(deep_scan=True)
            return {"errors": deep_errors if deep_errors else "Unknown logic contradiction. Check Concurrent Sets."}

    def run_diagnostics(self, deep_scan=False):
        report = []
        subject_requirements = self.session.query(SubjectRequirement).all()

        # 1. Check Section Totals
        section_totals = defaultdict(int)
        for req in subject_requirements:
            section_totals[req.class_section_id] += req.periods_per_week

        for sec_id, total in section_totals.items():
            sec = self.all_sections[sec_id]
            target = sec.periods_per_day * 5
            if total > target:
                report.append(f"❌ SECTION OVERLOAD: {sec.name} has {total} periods, but only {target} slots available.")

        # 2. Check Human Teacher Load vs. Student Availability
        human_loads = defaultdict(int)
        human_senior_loads = defaultdict(int)
        for req in subject_requirements:
            teacher_id = self.assignment_map.get((req.class_section_id, req.subject_id))
            if teacher_id:
                base_name = self.all_teachers[teacher_id].name.split(' (')[0]
                human_loads[base_name] += req.periods_per_week
                if self.all_sections[req.class_section_id].periods_per_day == 6:
                    human_senior_loads[base_name] += req.periods_per_week

        for name, load in human_loads.items():
            if load > 40:
                report.append(f"❌ PHYSICAL IMPOSSIBILITY: {name} assigned {load} periods. Max possible is 40.")
            elif human_senior_loads[name] > 30:
                # This is the "Suman Sharma" check.
                # If she has 35 senior periods, she MUST be in a Concurrent Set for at least 5 of them.
                needed_sync_periods = human_senior_loads[name] - 30
                report.append(
                    f"⚠️ TEACHER BOTTLENECK: {name} has {human_senior_loads[name]} senior periods but only 30 slots. You MUST ensure at least {needed_sync_periods} of these periods are in a 'Sync' Concurrent Set.")

        # 3. Check for "Set Overlaps" (The most common 0.17s failure)
        for cset in self.concurrent_sets:
            set_sections = [s.id for s in cset.sections]
            set_subjects = [s.id for s in cset.subjects]

            # Check if any section is forced to do TWO things at once by ONE set
            for sec_id in set_sections:
                subjects_for_sec_in_set = [sub_id for sub_id in set_subjects if (sec_id, sub_id) in self.assignment_map]
                if len(subjects_for_sec_in_set) > 1:
                    sub_names = [self.session.get(Subject, s_id).name for s_id in subjects_for_sec_in_set]
                    report.append(
                        f"❌ SET LOGIC ERROR: Set '{cset.name}' forces {self.all_sections[sec_id].name} to attend {sub_names} at the same time. This is impossible.")

        return "\n".join(report)

    def _define_variables_and_constraints(self):
        # We track intervals by both human and the specific teacher ID
        human_intervals = defaultdict(list)
        teacher_intervals = defaultdict(list)
        section_intervals = defaultdict(list)

        subject_requirements = self.session.query(SubjectRequirement).all()
        for req in subject_requirements:
            teacher_id = self.assignment_map.get((req.class_section_id, req.subject_id))
            if not teacher_id: continue

            section = self.all_sections[req.class_section_id]
            max_p_week = len(self.DAYS) * section.periods_per_day

            full_name = self.all_teachers[teacher_id].name
            base_human_name = full_name.split(' (')[0]

            for i in range(req.periods_per_week):
                prefix = f'L_{section.id}_{req.subject_id}_{teacher_id}_{i}'
                start_var = self.model.NewIntVar(0, max_p_week - 1, f'{prefix}_start')
                interval = self.model.NewIntervalVar(start_var, 1, start_var + 1, f'{prefix}_interval')
                self.class_periods[(section.id, req.subject_id, teacher_id, i)] = start_var

                # Add to all three tracking lists
                human_intervals[base_human_name].append(interval)
                teacher_intervals[teacher_id].append(interval)  # For individual teacher check
                section_intervals[section.id].append(interval)
                self.subject_class_vars[(req.class_section_id, req.subject_id)].append(start_var)

        # 1. Base Constraint: No section can be in two places at once.
        for intervals in section_intervals.values():
            self.model.AddNoOverlap(intervals)

        # 2. Build the Concurrent Set "Glue"
        var_to_cset_group_map = {}
        for cset in self.concurrent_sets:
            set_sec_ids = {s.id for s in cset.sections}
            set_sub_ids = {s.id for s in cset.subjects}
            groups = defaultdict(list)
            for (sec_id, sub_id, t_id, i), start_var in self.class_periods.items():
                if sec_id in set_sec_ids and sub_id in set_sub_ids:
                    groups[i].append(start_var)
            for i, vars_group in groups.items():
                if len(vars_group) > 1:
                    for other in vars_group[1:]: self.model.Add(other == vars_group[0])
                for v in vars_group: var_to_cset_group_map[v.Index()] = (cset.id, i)

        # 3. THE FIX: Prevent HUMAN overlap, but allow it for Concurrent Sets
        for name, intervals in human_intervals.items():
            # Filter out intervals that are part of the same concurrent group
            filtered_intervals = []
            handled_groups = set()
            for interval in intervals:
                idx = interval.StartExpr().Index()
                if idx not in var_to_cset_group_map:
                    filtered_intervals.append(interval)
                else:
                    group_id = var_to_cset_group_map[idx]
                    if group_id not in handled_groups:
                        filtered_intervals.append(interval)
                        handled_groups.add(group_id)

            if len(filtered_intervals) > 1:
                self.model.AddNoOverlap(filtered_intervals)

        # 4. Daily Subject Limit (Your "Max 2" rule)
        for req in subject_requirements:
            # ... (the max_per_day = 2 code from before goes here, it is correct)
            max_per_day = 3
            start_vars = self.subject_class_vars.get((req.class_section_id, req.subject_id))
            if not start_vars: continue
            section = self.all_sections[req.class_section_id]
            for day_idx in range(len(self.DAYS)):
                day_start = day_idx * section.periods_per_day
                day_end = (day_idx + 1) * section.periods_per_day - 1
                lits = []
                for var in start_vars:
                    lit = self.model.NewBoolVar(f'dist_{req.class_section_id}_{req.subject_id}_day_{day_idx}')
                    self.model.AddLinearExpressionInDomain(var, cp_model.Domain(day_start, day_end)).OnlyEnforceIf(lit)
                    self.model.AddLinearExpressionInDomain(var, cp_model.Domain.FromIntervals(
                        [[0, day_start - 1], [day_end + 1, 999]])).OnlyEnforceIf(lit.Not())
                    lits.append(lit)
                self.model.Add(sum(lits) <= max_per_day)
    def _extract_solution(self, solver):
        solution = {}
        for (section_id, subject_id, teacher_id, i), start_var in self.class_periods.items():
            slot_val = solver.Value(start_var)
            section = self.all_sections[section_id]
            max_p = section.periods_per_day
            day_val = self.DAYS[slot_val // max_p]
            period_val = slot_val % max_p + 1
            solution[(day_val, period_val, section_id)] = (subject_id, teacher_id)
        return solution


# endregion

# region: ================= UI DIALOGS & WIDGETS =================
class MultiSelectDialog(QDialog):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 500)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for item_text, item_data in items:
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, item_data)
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(list_item)

        layout.addWidget(self.list_widget)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_ids(self):
        selected_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_ids.append(item.data(Qt.UserRole))
        return selected_ids


class AssignmentDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Teacher Subject-Class Assignments")
        self.setMinimumSize(900, 700)
        self.all_teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        self.all_subjects = self.session.query(Subject).order_by(Subject.name).all()
        self.all_sections = self.session.query(ClassSection).order_by(ClassSection.name).all()
        self.main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        teacher_box = QGroupBox("1. Select a Teacher")
        teacher_layout = QVBoxLayout(teacher_box)
        self.teacher_filter = QLineEdit()
        self.teacher_filter.setPlaceholderText("Filter teachers...")
        self.teacher_list_widget = QListWidget()
        for teacher in self.all_teachers: item = QListWidgetItem(teacher.name); item.setData(Qt.UserRole,
                                                                                             teacher.id); self.teacher_list_widget.addItem(
            item)
        teacher_layout.addWidget(self.teacher_filter)
        teacher_layout.addWidget(self.teacher_list_widget)
        splitter.addWidget(teacher_box)
        self.assignment_box = QGroupBox("2. Assign Subjects and Classes")
        assignment_layout = QVBoxLayout(self.assignment_box)
        self.subject_filter = QLineEdit()
        self.subject_filter.setPlaceholderText("Filter subjects...")
        self.assignment_tree = QTreeWidget()
        self.assignment_tree.setHeaderHidden(True)
        assignment_layout.addWidget(self.subject_filter)
        assignment_layout.addWidget(self.assignment_tree)
        splitter.addWidget(self.assignment_box)
        splitter.setSizes([300, 600])
        self.main_layout.addWidget(splitter)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        self.main_layout.addWidget(buttons)
        self.teacher_filter.textChanged.connect(self.filter_teacher_list)
        self.subject_filter.textChanged.connect(self.filter_subject_tree)
        self.teacher_list_widget.currentItemChanged.connect(self.populate_assignment_tree)
        if self.all_teachers: self.teacher_list_widget.setCurrentRow(0)

    def filter_teacher_list(self, text):
        for i in range(self.teacher_list_widget.count()): self.teacher_list_widget.item(i).setHidden(
            text.lower() not in self.teacher_list_widget.item(i).text().lower())

    def filter_subject_tree(self, text):
        for i in range(self.assignment_tree.topLevelItemCount()): self.assignment_tree.topLevelItem(i).setHidden(
            text.lower() not in self.assignment_tree.topLevelItem(i).text(0).lower())

    def populate_assignment_tree(self, current_teacher_item, previous_item):
        self.assignment_tree.clear()
        if not current_teacher_item: self.assignment_box.setTitle("2. Assign Subjects and Classes"); return
        teacher_id = current_teacher_item.data(Qt.UserRole)
        self.assignment_box.setTitle(f"Assignments for {current_teacher_item.text()}")
        existing_assignments = self.session.query(TeacherAssignment).filter_by(teacher_id=teacher_id).all()
        assigned_pairs = {(a.subject_id, a.class_section_id) for a in existing_assignments}
        for subject in self.all_subjects:
            subject_item = QTreeWidgetItem()
            subject_item.setText(0, subject.name)
            subject_item.setData(0, Qt.UserRole, subject.id)
            subject_item.setFlags(subject_item.flags() | Qt.ItemIsSelectable)
            for section in self.all_sections:
                section_item = QTreeWidgetItem()
                section_item.setText(0, section.name)
                section_item.setData(0, Qt.UserRole, section.id)
                section_item.setFlags(section_item.flags() | Qt.ItemIsUserCheckable)
                if (subject.id, section.id) in assigned_pairs:
                    section_item.setCheckState(0, Qt.Checked)
                else:
                    section_item.setCheckState(0, Qt.Unchecked)
                subject_item.addChild(section_item)
            self.assignment_tree.addTopLevelItem(subject_item)

    def save_and_accept(self):
        current_teacher_item = self.teacher_list_widget.currentItem()
        if not current_teacher_item: QMessageBox.warning(self, "No Teacher Selected",
                                                         "Please select a teacher before saving."); return
        teacher_id = current_teacher_item.data(Qt.UserRole)
        self.session.query(TeacherAssignment).filter_by(teacher_id=teacher_id).delete()
        for i in range(self.assignment_tree.topLevelItemCount()):
            subject_item = self.assignment_tree.topLevelItem(i)
            subject_id = subject_item.data(0, Qt.UserRole)
            for j in range(subject_item.childCount()):
                section_item = subject_item.child(j)
                if section_item.checkState(0) == Qt.Checked:
                    section_id = section_item.data(0, Qt.UserRole)
                    conflict = self.session.query(TeacherAssignment).filter_by(subject_id=subject_id,
                                                                               class_section_id=section_id).first()
                    if conflict:
                        QMessageBox.warning(self, "Assignment Conflict",
                                            f"Cannot assign '{subject_item.text(0)}' to class '{section_item.text(0)}'.\nIt is already assigned to {conflict.teacher.name}.\nPlease un-assign it from the other teacher first.")
                        self.session.rollback()
                        return
                    self.session.add(
                        TeacherAssignment(teacher_id=teacher_id, subject_id=subject_id, class_section_id=section_id))
        self.session.commit()
        self.accept()


class ClassTeacherDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Manage Class Teachers")
        self.setMinimumSize(600, 700)
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Class Section", "Assigned Class Teacher"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_assignments)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        self.populate_table()

    def populate_table(self):
        sections = self.session.query(ClassSection).order_by(ClassSection.name).all()
        teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        self.table.setRowCount(len(sections))
        for row, section in enumerate(sections):
            section_item = QTableWidgetItem(section.name)
            section_item.setData(Qt.UserRole, section.id)
            section_item.setFlags(section_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, section_item)
            combo = QComboBox()
            combo.addItem("<< Unassigned >>", -1)
            for teacher in teachers: combo.addItem(teacher.name, teacher.id)
            if section.class_teacher_id:
                if (index := combo.findData(section.class_teacher_id)) != -1: combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(self.on_teacher_changed)
            self.table.setCellWidget(row, 1, combo)

    def on_teacher_changed(self, index):
        changed_combo = self.sender()
        teacher_id = changed_combo.currentData()
        if teacher_id == -1: return
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 1)
            if combo is not changed_combo and combo.currentData() == teacher_id:
                QMessageBox.warning(self, "Assignment Conflict",
                                    f"Teacher '{changed_combo.currentText()}' is already assigned. Please un-assign them first.")
                changed_combo.setCurrentIndex(0)
                return

    def save_assignments(self):
        for row in range(self.table.rowCount()):
            section = self.session.get(ClassSection, self.table.item(row, 0).data(Qt.UserRole))
            teacher_id = self.table.cellWidget(row, 1).currentData()
            section.class_teacher_id = None if teacher_id == -1 else teacher_id
        try:
            self.session.commit()
            self.accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Database Error",
                                 f"An error occurred while saving:\n{e}")


class RequirementsDialog(QDialog):
    def __init__(self, session, section, parent=None):
        super().__init__(parent)
        self.session = session
        self.section = section
        self.setWindowTitle(f"Weekly Subject Requirements for {section.name}")
        self.resize(500, 600)  # Set a reasonable default size

        # 1. Main Layout for the Dialog
        main_layout = QVBoxLayout(self)

        # 2. Create a Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # Allows the form to expand inside
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        # 3. Create a Container Widget to hold the Form
        content_widget = QWidget()
        self.form_layout = QFormLayout(content_widget)

        # 4. Add specific logic to populate the form
        self.subjects = self.session.query(Subject).order_by(Subject.name).all()
        self.spin_boxes = {}

        for sub in self.subjects:
            req = self.session.query(SubjectRequirement).filter_by(
                class_section_id=self.section.id,
                subject_id=sub.id
            ).first()

            sb = QSpinBox()
            sb.setRange(0, self.section.periods_per_day * 5)
            sb.setValue(req.periods_per_week if req else 0)
            self.spin_boxes[sub.id] = sb
            self.form_layout.addRow(f"{sub.name}:", sb)

        # 5. Set the container into the scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # 6. Add Buttons at the bottom (outside the scroll area)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_requirements)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def save_requirements(self):
        total_periods = sum(sb.value() for sb in self.spin_boxes.values())
        for sub_id, sb in self.spin_boxes.items():
            req = self.session.query(SubjectRequirement).filter_by(
                class_section_id=self.section.id,
                subject_id=sub_id
            ).first()

            if sb.value() > 0:
                if req:
                    req.periods_per_week = sb.value()
                else:
                    self.session.add(SubjectRequirement(
                        class_section_id=self.section.id,
                        subject_id=sub_id,
                        periods_per_week=sb.value()
                    ))
            elif req:
                self.session.delete(req)

        required_total = self.section.periods_per_day * 5
        if total_periods != required_total:
            QMessageBox.warning(
                self,
                "Check Totals",
                f"The total periods specified ({total_periods}) does not match the required total for the week ({required_total}).\n"
                f"The generator will fail if these do not match."
            )
        self.session.commit()
        self.accept()


class ConcurrentSetDialog(QDialog):
    def __init__(self, session, set_id=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.set_id = set_id
        self.cset = self.session.get(ConcurrentSet, self.set_id) if self.set_id else None
        self.setWindowTitle("Edit Concurrent Set" if self.cset else "Create Concurrent Set")
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.name_edit = QLineEdit(self.cset.name if self.cset else "")
        self.color_edit = QLineEdit(self.cset.color if self.cset else "#FFCCCB")
        form_layout.addRow("Set Name:", self.name_edit)
        form_layout.addRow("Set Color (e.g., lightblue or #add8e6):", self.color_edit)
        self.layout.addLayout(form_layout)
        splitter = QSplitter(Qt.Horizontal)
        sec_box = QGroupBox("Sections")
        sec_vbox = QVBoxLayout(sec_box)
        self.sections_list = QListWidget()
        self.sections_list.setSelectionMode(QListWidget.ExtendedSelection)
        sections_in_set = {s.id for s in self.cset.sections} if self.cset else set()
        for sec in self.session.query(ClassSection).order_by(ClassSection.name).all():
            item = QListWidgetItem(sec.name)
            item.setData(Qt.UserRole, sec.id)
            self.sections_list.addItem(item)
            if sec.id in sections_in_set:
                item.setSelected(True)
        sec_vbox.addWidget(self.sections_list)
        splitter.addWidget(sec_box)
        sub_box = QGroupBox("Subjects")
        sub_vbox = QVBoxLayout(sub_box)
        self.subjects_list = QListWidget()
        self.subjects_list.setSelectionMode(QListWidget.ExtendedSelection)
        subjects_in_set = {s.id for s in self.cset.subjects} if self.cset else set()
        for sub in self.session.query(Subject).order_by(Subject.name).all():
            item = QListWidgetItem(sub.name)
            item.setData(Qt.UserRole, sub.id)
            self.subjects_list.addItem(item)
            if sub.id in subjects_in_set:
                item.setSelected(True)
        sub_vbox.addWidget(self.subjects_list)
        splitter.addWidget(sub_box)
        self.layout.addWidget(splitter)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)

    def save_set(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Set name cannot be empty.")
            return False
        existing_set = self.session.query(ConcurrentSet).filter(ConcurrentSet.name.ilike(name)).first()
        if existing_set and (not self.cset or existing_set.id != self.cset.id):
            QMessageBox.warning(self, "Input Error", "A set with this name already exists.")
            return False
        if not self.cset:
            self.cset = ConcurrentSet(name=name)
            self.session.add(self.cset)
        self.cset.name = name
        self.cset.color = self.color_edit.text().strip() or "#FFCCCB"
        self.cset.sections = [self.session.get(ClassSection, item.data(Qt.UserRole)) for item in
                              self.sections_list.selectedItems()]
        self.cset.subjects = [self.session.get(Subject, item.data(Qt.UserRole)) for item in
                              self.subjects_list.selectedItems()]
        self.session.commit()
        return True

    def accept(self):
        if self.save_set(): super().accept()


# endregion

class TimetableApp(QMainWindow):
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    MIN_PERIODS, MAX_PERIODS = 1, 16

    def __init__(self, session, spinner_path="spinner.gif"):
        super().__init__()
        self.session = session
        self.spinner_path = spinner_path
        self.setWindowTitle("School Timetable Generator")
        self.setMinimumSize(1280, 800)
        self.setup_ui()
        self.connect_signals()
        self.nav_tree.setCurrentItem(self.nav_tree.topLevelItem(0))
        self.refresh_all_data()
        self.worker_thread = None

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QHBoxLayout(self.central_widget)
        self.nav_tree = QTreeWidget()
        self.nav_tree.setFixedWidth(200)
        self.nav_tree.setHeaderHidden(True)
        main_layout.addWidget(self.nav_tree)
        self.pages_stack = QStackedWidget()
        main_layout.addWidget(self.pages_stack)
        self.add_nav_page("Dashboard", self.create_dashboard_page())
        self.add_nav_page("Setup", self.create_setup_page())
        self.add_nav_page("Manage", self.create_manage_page())
        self.add_nav_page("Generator", self.create_generator_page())
        tt_page_parent = self.add_nav_page("Timetables", is_parent=True)
        self.add_nav_page("Class Timetables", self.create_class_tt_page(), parent=tt_page_parent)
        self.add_nav_page("Teacher Timetables", self.create_teacher_tt_page(), parent=tt_page_parent)
        self.add_nav_page("Master Teacher View", self.create_master_teacher_tt_page(), parent=tt_page_parent)
        self.nav_tree.expandAll()

    def add_nav_page(self, name, widget=None, parent=None, is_parent=False):
        if parent:
            item = QTreeWidgetItem(parent, [name])
        else:
            item = QTreeWidgetItem(self.nav_tree, [name])
        if not is_parent:
            item.setData(1, Qt.UserRole, self.pages_stack.count())
            self.pages_stack.addWidget(widget)
        return item

    def switch_page(self, item, column):
        page_index = item.data(1, Qt.UserRole)
        if page_index is not None: self.pages_stack.setCurrentIndex(page_index)

    def connect_signals(self):
        self.nav_tree.currentItemChanged.connect(self.switch_page)
        self.mg_tabs.currentChanged.connect(self.refresh_manage_lists)
        self.add_btn.clicked.connect(self.add_item)
        self.edit_btn.clicked.connect(self.edit_item)
        self.del_btn.clicked.connect(self.delete_item)
        self.assign_btn.clicked.connect(self.open_assignment_dialog)
        self.manage_ct_btn.clicked.connect(self.open_class_teacher_dialog)
        self.manage_reqs_btn.clicked.connect(self.open_requirements_dialog)
        self.req_section_combo.currentIndexChanged.connect(self.update_req_button_state)
        self.add_cset_btn.clicked.connect(self.add_concurrent_set)
        self.edit_cset_btn.clicked.connect(self.edit_concurrent_set)
        self.del_cset_btn.clicked.connect(self.delete_concurrent_set)
        self.generate_btn.clicked.connect(self.run_logic_generator)
        self.class_tt_section_combo.currentIndexChanged.connect(self.update_class_timetable_grid)
        self.teacher_tt_combo.currentIndexChanged.connect(self.update_teacher_timetable_grid)
        self.export_class_tt_btn.clicked.connect(self.export_class_timetables)
        self.export_teacher_tt_btn.clicked.connect(self.export_teacher_timetables)
        self.export_master_tt_btn.clicked.connect(self.export_master_timetable)

    def create_dashboard_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.addStretch(1)
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            vbox.addWidget(logo_label)
        lbl = QLabel("📅 HPS Timetable Generator")
        lbl.setFont(QFont("Arial", 28, QFont.Bold))
        lbl.setAlignment(Qt.AlignCenter)
        vbox.addWidget(lbl)
        desc = QLabel(
            "An automated school timetable scheduler using constraint satisfaction.\n\nNavigate using the menu on the left:\n1. Add data in 'Manage'.\n2. Configure rules in 'Setup'.\n3. Create a schedule in 'Generator'.\n4. View results in 'Timetables'.")
        desc.setFont(QFont("Arial", 13))
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        vbox.addWidget(desc)
        vbox.addStretch(2)
        return page

    def create_manage_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        self.mg_tabs = QTabWidget()
        self.teachers_list = QListWidget()
        self.subjects_list = QListWidget()
        self.sections_list = QListWidget()
        self.mg_tabs.addTab(self.teachers_list, "Teachers")
        self.mg_tabs.addTab(self.subjects_list, "Subjects")
        self.mg_tabs.addTab(self.sections_list, "Class Sections")
        btns_vbox = QVBoxLayout()
        self.add_btn = QPushButton("Add New")
        self.edit_btn = QPushButton("Edit Selected")
        self.del_btn = QPushButton("Delete Selected")
        btns_vbox.addWidget(self.add_btn)
        btns_vbox.addWidget(self.edit_btn)
        btns_vbox.addWidget(self.del_btn)
        btns_vbox.addStretch()
        layout.addWidget(self.mg_tabs, 3)
        layout.addLayout(btns_vbox, 1)
        return page

    def create_setup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        assign_box = QGroupBox("1. Manage Assignments")
        assign_layout = QHBoxLayout(assign_box)
        self.assign_btn = QPushButton("Assign Subjects to Classes")
        self.manage_ct_btn = QPushButton("Assign Class Teachers")
        assign_layout.addWidget(self.assign_btn)
        assign_layout.addWidget(self.manage_ct_btn)
        layout.addWidget(assign_box)
        req_box = QGroupBox("2. Set Weekly Subject Requirements per Class")
        req_layout = QHBoxLayout(req_box)
        self.req_section_combo = QComboBox()
        self.manage_reqs_btn = QPushButton("Manage Requirements for Selected Class")
        req_layout.addWidget(QLabel("Class Section:"))
        req_layout.addWidget(self.req_section_combo, 1)
        req_layout.addWidget(self.manage_reqs_btn, 2)
        layout.addWidget(req_box)
        cset_box = QGroupBox("3. Define Concurrent Sets (for Skill/Optional Subjects)")
        cset_layout = QHBoxLayout(cset_box)
        self.cset_list = QListWidget()
        cset_layout.addWidget(self.cset_list)
        cset_btns_vbox = QVBoxLayout()
        self.add_cset_btn = QPushButton("Add New Set")
        self.edit_cset_btn = QPushButton("Edit Selected Set")
        self.del_cset_btn = QPushButton("Delete Selected Set")
        cset_btns_vbox.addWidget(self.add_cset_btn)
        cset_btns_vbox.addWidget(self.edit_cset_btn)
        cset_btns_vbox.addWidget(self.del_cset_btn)
        cset_btns_vbox.addStretch()
        cset_layout.addLayout(cset_btns_vbox)
        layout.addWidget(cset_box)
        layout.addStretch()
        return page

    def create_generator_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        self.generate_btn = QPushButton("Generate Timetable")
        self.generate_btn.setMinimumHeight(60)
        self.generate_btn.setFont(QFont("Arial", 16))
        self.status_label = QLabel("Click the button to start the generation process.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.spinner_label = QLabel()
        self.spinner_movie = QMovie(self.spinner_path)
        self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.setAlignment(Qt.AlignCenter)
        self.spinner_label.hide()
        layout.addStretch(1)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.spinner_label)
        layout.addWidget(self.status_label)
        layout.addStretch(2)
        return page

    def create_class_tt_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        controls_box = QGroupBox("Select View")
        controls_layout = QHBoxLayout(controls_box)
        self.class_tt_section_combo = QComboBox()
        self.class_periods_label = QLabel()
        self.export_class_tt_btn = QPushButton("Export to PDF")
        controls_layout.addWidget(QLabel("Section:"))
        controls_layout.addWidget(self.class_tt_section_combo, 2)
        controls_layout.addWidget(self.class_periods_label, 1)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.export_class_tt_btn, 1)
        layout.addWidget(controls_box)
        self.class_tt_grid = QTableWidget()
        self.class_tt_grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.class_tt_grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.class_tt_grid.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.class_tt_grid)
        return page

    def create_teacher_tt_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        controls_box = QGroupBox("Select View")
        controls_layout = QHBoxLayout(controls_box)
        self.teacher_tt_combo = QComboBox()
        self.export_teacher_tt_btn = QPushButton("Export to PDF")
        controls_layout.addWidget(QLabel("Teacher:"))
        controls_layout.addWidget(self.teacher_tt_combo, 2)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.export_teacher_tt_btn, 1)
        layout.addWidget(controls_box)
        self.teacher_tt_grid = QTableWidget()
        self.teacher_tt_grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.teacher_tt_grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.teacher_tt_grid.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.teacher_tt_grid)
        return page

    # --- THIS IS THE MISSING FUNCTION THAT HAS BEEN RESTORED ---
    def create_master_teacher_tt_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        controls_layout = QHBoxLayout()
        title = QLabel("Master Teacher Timetable (Staff Deployment)")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        controls_layout.addWidget(title)
        controls_layout.addStretch()
        self.export_master_tt_btn = QPushButton("Export to PDF")
        controls_layout.addWidget(self.export_master_tt_btn)

        layout.addLayout(controls_layout)

        self.master_teacher_tt_grid = QTableWidget()
        self.master_teacher_tt_grid.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.master_teacher_tt_grid)
        return page

    def refresh_all_data(self):
        self.refresh_manage_lists()
        self.refresh_setup_page_combos()
        self.refresh_cset_list()
        self.refresh_timetable_combos()
        self.update_class_timetable_grid()
        self.update_teacher_timetable_grid()
        self.update_master_teacher_tt_grid()

    def refresh_manage_lists(self, index=0):
        self.teachers_list.clear()
        [self.teachers_list.addItem(QListWidgetItem(t.name)) for t in
         self.session.query(Teacher).order_by(Teacher.name)]
        self.subjects_list.clear()
        [self.subjects_list.addItem(QListWidgetItem(s.name)) for s in
         self.session.query(Subject).order_by(Subject.name)]
        # ... inside refresh_manage_lists ...
        self.sections_list.clear()
        # Query all sections, but we'll manually filter to show unique display names
        all_sections = self.session.query(ClassSection).order_by(ClassSection.name).all()
        displayed_sections = {}  # Use a dict to store the main section for each display name

        for sec in all_sections:
            display = sec.display_name or sec.name
            if display not in displayed_sections:
                # Find the "main" section object that matches the display name
                main_sec = self.session.query(ClassSection).filter_by(name=display).first()
                if main_sec:
                    displayed_sections[display] = main_sec

        # Now add the unique, main sections to the list
        for display, sec_obj in sorted(displayed_sections.items()):
            teacher_name = f" (CT: {sec_obj.class_teacher.name})" if sec_obj.class_teacher else ""
            item_text = f"{display} ({sec_obj.periods_per_day} periods/day){teacher_name}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, sec_obj.id)
            self.sections_list.addItem(item)

    def refresh_setup_page_combos(self):
        self.req_section_combo.clear()
        [self.req_section_combo.addItem(sec.name, sec.id) for sec in
         self.session.query(ClassSection).order_by(ClassSection.name).all()]
        self.update_req_button_state()

    def refresh_cset_list(self):
        self.cset_list.clear()
        for cset in self.session.query(ConcurrentSet).order_by(ConcurrentSet.name).all():
            item = QListWidgetItem(cset.name)
            item.setData(Qt.UserRole, cset.id)
            self.cset_list.addItem(item)

    def refresh_timetable_combos(self):
        self.class_tt_section_combo.blockSignals(True)
        self.teacher_tt_combo.blockSignals(True)

        # --- CLEAN CLASS DROPDOWN (Shows "11 Sci" once) ---
        self.class_tt_section_combo.clear()
        all_sections = self.session.query(ClassSection).order_by(ClassSection.name).all()
        displayed_classes = {}
        for sec in all_sections:
            display = sec.display_name or sec.name
            if display not in displayed_classes:
                displayed_classes[display] = sec.id  # Keep the ID of the first one found
        for display_name, sid in sorted(displayed_classes.items()):
            self.class_tt_section_combo.addItem(display_name, sid)

        # --- CLEAN TEACHER DROPDOWN (Shows "Suman Sharma" once) ---
        self.teacher_tt_combo.clear()
        all_teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        unique_teacher_names = sorted(list(set([t.name.split(' (')[0] for t in all_teachers])))
        for name in unique_teacher_names:
            # We store the base name string so the grid can search for all variants
            self.teacher_tt_combo.addItem(name, name)

        self.class_tt_section_combo.blockSignals(False)
        self.teacher_tt_combo.blockSignals(False)

    def _get_current_manage_info(self):
        idx = self.mg_tabs.currentIndex()
        if idx == 0: return Teacher, self.teachers_list, "Teacher"
        if idx == 1: return Subject, self.subjects_list, "Subject"
        if idx == 2: return ClassSection, self.sections_list, "Class Section"
        return None, None, None
    def add_item(self):
        Model, _, model_name = self._get_current_manage_info()
        if not Model: return
        if Model == ClassSection:
            name, ok = QInputDialog.getText(self, f"Add {model_name}", f"{model_name} Name:")
            if not (ok and name.strip()): return
            periods, ok = QInputDialog.getInt(self, "Periods per Day", "How many?", 8, self.MIN_PERIODS,
                                              self.MAX_PERIODS)
            if not ok: return
            instance = Model(name=name.strip(), periods_per_day=periods)
        else:
            name, ok = QInputDialog.getText(self, f"Add {model_name}", f"{model_name} Name:")
            if not (ok and name.strip()): return
            instance = Model(name=name.strip())
        if self.session.query(Model).filter(Model.name.ilike(name.strip())).first(): QMessageBox.warning(self, "Exists",
                                                                                                         f"A {model_name} with that name already exists."); return
        self.session.add(instance)
        self.session.commit()
        self.refresh_all_data()

    def edit_item(self):
        Model, list_widget, model_name = self._get_current_manage_info()
        if not Model or not list_widget.currentItem(): return
        item_text = list_widget.currentItem().text().split(" (")[0]
        if Model == ClassSection:
            instance = self.session.get(ClassSection, list_widget.currentItem().data(Qt.UserRole))
        else:
            instance = self.session.query(Model).filter_by(name=item_text).first()
        if not instance: return
        new_name, ok = QInputDialog.getText(self, f"Edit {model_name}", "New Name:", text=instance.name)
        if ok and new_name.strip():
            if self.session.query(Model).filter(Model.name.ilike(new_name.strip()),
                                                Model.id != instance.id).first(): QMessageBox.warning(self, "Exists",
                                                                                                      f"A {model_name} with that name already exists."); return
            instance.name = new_name.strip()
        if Model == ClassSection:
            new_periods, ok = QInputDialog.getInt(self, "Edit Periods", "Periods per day:", instance.periods_per_day,
                                                  self.MIN_PERIODS, self.MAX_PERIODS)
            if ok: instance.periods_per_day = new_periods
        self.session.commit()
        self.refresh_all_data()

    def delete_item(self):
        Model, list_widget, model_name = self._get_current_manage_info()
        if not Model or not list_widget.currentItem(): return
        item_text = list_widget.currentItem().text().split(" (")[0]
        if Model == ClassSection:
            instance = self.session.get(ClassSection, list_widget.currentItem().data(Qt.UserRole))
        else:
            instance = self.session.query(Model).filter_by(name=item_text).first()
        if not instance: return
        if QMessageBox.question(self, f"Delete {model_name}", f"Delete '{instance.name}'?",
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes: self.session.delete(
            instance); self.session.commit(); self.refresh_all_data()

    def open_assignment_dialog(self):
        dlg = AssignmentDialog(self.session, self)
        dlg.exec()

    def open_class_teacher_dialog(self):
        dlg = ClassTeacherDialog(self.session, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all_data()

    def update_req_button_state(self):
        self.manage_reqs_btn.setEnabled(self.req_section_combo.count() > 0)

    def open_requirements_dialog(self):
        sec_id = self.req_section_combo.currentData()
        if not sec_id:
            QMessageBox.warning(self, "No Section", "Please select a class section.")
            return
        section = self.session.get(ClassSection, sec_id)
        dlg = RequirementsDialog(self.session, section, self)
        dlg.exec()

    def add_concurrent_set(self):
        dlg = ConcurrentSetDialog(self.session, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_cset_list()

    def edit_concurrent_set(self):
        item = self.cset_list.currentItem()
        if not item: return
        dlg = ConcurrentSetDialog(self.session, set_id=item.data(Qt.UserRole), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_cset_list()

    def delete_concurrent_set(self):
        item = self.cset_list.currentItem()
        if not item: return
        cset = self.session.get(ConcurrentSet, item.data(Qt.UserRole))
        if QMessageBox.question(self, f"Delete Set", f"Delete '{cset.name}'?", QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            self.session.delete(cset)
            self.session.commit()
            self.refresh_cset_list()

    def run_logic_generator(self):
        if QMessageBox.question(self, "Confirm", "This will clear the current timetable. Proceed?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating... Please wait.")
        self.spinner_label.show()
        self.spinner_movie.start()
        self.worker_thread = QThread()
        self.worker = SolverWorker(TimetableSolver(self.session))
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_generation_complete)
        self.worker.error.connect(self.on_generation_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def on_generation_complete(self, solution):
        # Handle Diagnostic Errors
        if isinstance(solution, dict) and "errors" in solution:
            self.generate_btn.setEnabled(True)
            self.status_label.setText("Generation failed.")
            self.spinner_movie.stop();
            self.spinner_label.hide()
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Data Logic Errors")
            msg.setText("Conflicts found:")
            msg.setInformativeText(solution["errors"])
            msg.exec()
            return

        # Handle Success
        if solution:
            Session = sessionmaker(bind=self.session.get_bind())
            db_session = Session()
            try:
                db_session.query(ScheduleEntry).delete()
                for (day, period, section_id), (subject_id, teacher_id) in solution.items():
                    db_session.add(
                        ScheduleEntry(class_section_id=section_id, subject_id=subject_id, teacher_id=teacher_id,
                                      day=day, period=period))
                db_session.commit()
                self.refresh_all_data()
                QMessageBox.information(self, "Success", "Timetable generated!")
            except Exception as e:
                db_session.rollback()
                QMessageBox.critical(self, "Error", f"Save failed: {e}")
            finally:
                db_session.close()
        else:
            QMessageBox.critical(self, "Failed", "No solution found.")

        self.generate_btn.setEnabled(True)
        self.status_label.setText("Generation complete.")
        self.spinner_movie.stop();
        self.spinner_label.hide()

    def on_generation_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        self.generate_btn.setEnabled(True)
        self.status_label.setText("An error occurred.")
        self.spinner_movie.stop()
        self.spinner_label.hide()

    def update_class_timetable_grid(self):
        main_section_id = self.class_tt_section_combo.currentData()
        if not main_section_id: return

        main_sec = self.session.get(ClassSection, main_section_id)
        display_name_to_show = main_sec.display_name or main_sec.name

        self.class_periods_label.setText(f"({main_sec.periods_per_day} periods/day)")
        self.class_tt_grid.setRowCount(main_sec.periods_per_day)
        self.class_tt_grid.setColumnCount(len(self.DAYS))
        self.class_tt_grid.setHorizontalHeaderLabels(self.DAYS)

        section_ids = [s.id for s in self.session.query(ClassSection).filter(
            (ClassSection.display_name == display_name_to_show) | (ClassSection.name == display_name_to_show)
        ).all()]

        all_entries = self.session.query(ScheduleEntry).filter(ScheduleEntry.class_section_id.in_(section_ids)).all()

        merged_schedule = defaultdict(list)
        for entry in all_entries:
            merged_schedule[(entry.day, entry.period)].append(entry)

        # --- CONCURRENT SET NAME FIX: Build a map to find set info ---
        set_info_map = {}
        for cset in self.session.query(ConcurrentSet).all():
            for section in cset.sections:
                for subject in cset.subjects:
                    set_info_map[(section.id, subject.id)] = (cset.name, cset.color)

        for r in range(main_sec.periods_per_day):
            for c, day in enumerate(self.DAYS):
                entries = merged_schedule.get((day, r + 1))
                item = QTableWidgetItem("")

                if entries:
                    unique_parts = {}
                    bg_color = QColor("#FFFFFF")

                    # Check if the first entry is part of ANY concurrent set for this time slot
                    is_concurrent_slot = any((e.class_section_id, e.subject_id) in set_info_map for e in entries)

                    if is_concurrent_slot:
                        # If it's a concurrent slot, use the SET name and color
                        first_entry = entries[0]
                        set_name, set_color = set_info_map.get((first_entry.class_section_id, first_entry.subject_id),
                                                               ("Concurrent", "#FFCCCB"))
                        item.setText(set_name)
                        item.setBackground(QColor(set_color))
                    else:
                        # Otherwise, use the normal subject/teacher display
                        for entry in entries:
                            clean_t_name = entry.teacher.name.split(' (')[0]
                            display_text = f"{entry.subject.name}\n({clean_t_name})"
                            unique_parts[entry.subject.name] = display_text

                        final_text = " / ".join(sorted(unique_parts.values()))
                        item.setText(final_text)
                        if entries[0].subject:
                            bg_color = QColor(entries[0].subject.color or "#E0E0E0")
                        item.setBackground(bg_color)

                item.setTextAlignment(Qt.AlignCenter)
                self.class_tt_grid.setItem(r, c, item)
    def update_teacher_timetable_grid(self):
        base_name = self.teacher_tt_combo.currentData()
        if not base_name or not isinstance(base_name, str): return

        # --- LOGIC: Find ALL IDs that belong to this teacher ---
        teacher_ids = [t.id for t in self.session.query(Teacher).filter(Teacher.name.like(f"{base_name}%")).all()]

        max_periods = max((s.periods_per_day for s in self.session.query(ClassSection).all()), default=8)
        self.teacher_tt_grid.setRowCount(max_periods)
        self.teacher_tt_grid.setColumnCount(len(self.DAYS))
        self.teacher_tt_grid.setHorizontalHeaderLabels(self.DAYS)

        # Query entries for ALL matching teacher IDs
        schedule = {(e.day, e.period): e for e in
                    self.session.query(ScheduleEntry).filter(ScheduleEntry.teacher_id.in_(teacher_ids)).all()}

        for r in range(max_periods):
            for c, day in enumerate(self.DAYS):
                entry = schedule.get((day, r + 1))
                txt = f"{entry.subject.name}\n({entry.class_section.display_name or entry.class_section.name})" if entry else ""
                item = QTableWidgetItem(txt)
                if entry: item.setBackground(QColor(entry.subject.color or "#E0E0E0"))
                item.setTextAlignment(Qt.AlignCenter)
                self.teacher_tt_grid.setItem(r, c, item)

    def update_master_teacher_tt_grid(self):
        self.master_teacher_tt_grid.clear()
        all_teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        if not all_teachers:
            self.master_teacher_tt_grid.setRowCount(0)
            self.master_teacher_tt_grid.setColumnCount(0)
            return
        teacher_map = {teacher.id: i for i, teacher in enumerate(all_teachers)}
        max_periods = max((s.periods_per_day for s in self.session.query(ClassSection).all()), default=8)
        self.master_teacher_tt_grid.setColumnCount(len(all_teachers))
        self.master_teacher_tt_grid.setHorizontalHeaderLabels([t.name for t in all_teachers])
        total_rows = len(self.DAYS) * max_periods
        self.master_teacher_tt_grid.setRowCount(total_rows)
        v_headers = []
        for day in self.DAYS:
            for p in range(max_periods):
                v_headers.append(f"{day[:3]} - P{p + 1}")
        self.master_teacher_tt_grid.setVerticalHeaderLabels(v_headers)
        schedule_map = {(e.day, e.period, e.teacher_id): e for e in self.session.query(ScheduleEntry).all()}
        row_index = 0
        for day in self.DAYS:
            for period in range(1, max_periods + 1):
                for teacher in all_teachers:
                    col_index = teacher_map[teacher.id]
                    entry = schedule_map.get((day, period, teacher.id))
                    if entry and entry.subject and entry.class_section:
                        item_text = f"{entry.subject.name}\n({entry.class_section.name})"
                        bg_color = QColor(entry.subject.color or "#E0E0E0")
                    else:
                        item_text = ""
                        bg_color = QColor("#FFFFFF")
                    item = QTableWidgetItem(item_text)
                    item.setBackground(bg_color)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.master_teacher_tt_grid.setItem(row_index, col_index, item)
                row_index += 1
        self.master_teacher_tt_grid.resizeRowsToContents()

    def export_class_timetables(self):
        all_sections = self.session.query(ClassSection).order_by(ClassSection.name).all()
        if not all_sections:
            QMessageBox.warning(self, "No Data", "There are no class sections to export.")
            return
        items = [(s.name, s.id) for s in all_sections]
        dialog = MultiSelectDialog("Select Classes to Export", items, self)
        current_id = self.class_tt_section_combo.currentData()
        if current_id:
            for i in range(dialog.list_widget.count()):
                item = dialog.list_widget.item(i)
                if item.data(Qt.UserRole) == current_id:
                    item.setCheckState(Qt.Checked)
                    break
        if dialog.exec() == QDialog.Accepted:
            selected_ids = dialog.get_selected_ids()
            if not selected_ids: return
            path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if not path: return
            timetables_data = []
            for sid in selected_ids:
                section = self.session.get(ClassSection, sid)
                data, max_periods = self._get_class_timetable_data(sid)
                timetables_data.append({
                    "title": f"Timetable for Class: {section.name}",
                    "data": data,
                    "max_periods": max_periods
                })
            self._write_timetables_to_pdf(path, timetables_data)

    def export_teacher_timetables(self):
        all_teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        if not all_teachers:
            QMessageBox.warning(self, "No Data", "There are no teachers to export.")
            return
        items = [(t.name, t.id) for t in all_teachers]
        dialog = MultiSelectDialog("Select Teachers to Export", items, self)
        current_id = self.teacher_tt_combo.currentData()
        if current_id:
            for i in range(dialog.list_widget.count()):
                item = dialog.list_widget.item(i)
                if item.data(Qt.UserRole) == current_id:
                    item.setCheckState(Qt.Checked)
                    break
        if dialog.exec() == QDialog.Accepted:
            selected_ids = dialog.get_selected_ids()
            if not selected_ids: return
            path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if not path: return
            timetables_data = []
            max_periods_overall = max((s.periods_per_day for s in self.session.query(ClassSection).all()), default=8)
            for tid in selected_ids:
                teacher = self.session.get(Teacher, tid)
                data, _ = self._get_teacher_timetable_data(tid, max_periods_overall)
                timetables_data.append({
                    "title": f"Timetable for Teacher: {teacher.name}",
                    "data": data,
                    "max_periods": max_periods_overall
                })
            self._write_timetables_to_pdf(path, timetables_data)

    def export_master_timetable(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Master Timetable PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        data, h_headers, v_headers = self._get_master_timetable_data()
        if not h_headers:
            QMessageBox.warning(self, "No Data", "There are no teachers to export in the master timetable.")
            return
        self._write_master_timetable_to_pdf(path, data, h_headers, v_headers)

    def _get_class_timetable_data(self, section_id):
        section = self.session.get(ClassSection, section_id)
        grid_data = [["" for _ in self.DAYS] for _ in range(section.periods_per_day)]
        set_info_map = {}
        for cset in self.session.query(ConcurrentSet).all():
            for subject in cset.subjects:
                for sec in cset.sections:
                    set_info_map[(subject.id, sec.id)] = (cset.name, cset.color)
        schedule = {(e.day, e.period): e for e in
                    self.session.query(ScheduleEntry).filter_by(class_section_id=section_id).all()}
        for r in range(section.periods_per_day):
            for c, day in enumerate(self.DAYS):
                entry = schedule.get((day, r + 1))
                cell_text, cell_color = "", "#FFFFFF"
                if entry and entry.subject and entry.teacher:
                    lookup_key = (entry.subject.id, entry.class_section_id)
                    if lookup_key in set_info_map:
                        cell_text = set_info_map[lookup_key][0]
                        cell_color = set_info_map[lookup_key][1] or "#FFCCCB"
                    else:
                        cell_text = f"{entry.subject.name}\n({entry.teacher.name})"
                        cell_color = entry.subject.color or "#E0E0E0"
                grid_data[r][c] = (cell_text, cell_color)
        return grid_data, section.periods_per_day

    def _get_teacher_timetable_data(self, teacher_id, max_periods):
        grid_data = [["" for _ in self.DAYS] for _ in range(max_periods)]
        schedule = {(e.day, e.period): e for e in
                    self.session.query(ScheduleEntry).filter_by(teacher_id=teacher_id).all()}
        for r in range(max_periods):
            for c, day in enumerate(self.DAYS):
                entry = schedule.get((day, r + 1))
                cell_text, cell_color = "", "#FFFFFF"
                if entry and entry.subject and entry.class_section:
                    cell_text = f"{entry.subject.name}\n({entry.class_section.name})"
                    cell_color = entry.subject.color or "#E0E0E0"
                grid_data[r][c] = (cell_text, cell_color)
        return grid_data, max_periods

    def _get_master_timetable_data(self):
        all_teachers = self.session.query(Teacher).order_by(Teacher.name).all()
        if not all_teachers:
            return [], [], []
        teacher_map = {teacher.id: i for i, teacher in enumerate(all_teachers)}
        h_headers = [t.name for t in all_teachers]
        max_periods = max((s.periods_per_day for s in self.session.query(ClassSection).all()), default=8)
        total_rows = len(self.DAYS) * max_periods
        v_headers = []
        for day in self.DAYS:
            for p in range(max_periods):
                v_headers.append(f"{day[:3]} - P{p + 1}")
        grid_data = [[("", "#FFFFFF") for _ in all_teachers] for _ in range(total_rows)]
        schedule_map = {(e.day, e.period, e.teacher_id): e for e in self.session.query(ScheduleEntry).all()}
        row_index = 0
        for day in self.DAYS:
            for period in range(1, max_periods + 1):
                for teacher in all_teachers:
                    col_index = teacher_map[teacher.id]
                    entry = schedule_map.get((day, period, teacher.id))
                    if entry and entry.subject and entry.class_section:
                        item_text = f"{entry.subject.name}\n({entry.class_section.name})"
                        bg_color = entry.subject.color or "#E0E0E0"
                        grid_data[row_index][col_index] = (item_text, bg_color)
                row_index += 1
        return grid_data, h_headers, v_headers

    def _write_timetables_to_pdf(self, file_path, timetables_data):
        try:
            doc = SimpleDocTemplate(file_path, pagesize=(11 * inch, 8.5 * inch))
            styles = getSampleStyleSheet()
            story = []
            for i, tt in enumerate(timetables_data):
                story.append(Paragraph(tt['title'], styles['h1']))
                story.append(Spacer(1, 0.2 * inch))
                table_data = []
                headers = ["Period"] + self.DAYS
                table_data.append(headers)
                for r in range(tt['max_periods']):
                    row_data = [f"Period {r + 1}"]
                    for c in range(len(self.DAYS)):
                        cell_content, _ = tt['data'][r][c]
                        row_data.append(Paragraph(cell_content.replace('\n', '<br/>'), styles['Normal']))
                    table_data.append(row_data)
                table = ReportLabTable(table_data, colWidths=[0.8 * inch] + [2 * inch] * 5)
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (0, -1), colors.beige),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ])
                for r in range(tt['max_periods']):
                    for c in range(len(self.DAYS)):
                        _, cell_color_hex = tt['data'][r][c]
                        if cell_color_hex and cell_color_hex != "#FFFFFF":
                            try:
                                qcolor = QColor(cell_color_hex)
                                cell_color = colors.Color(qcolor.redF(), qcolor.greenF(), qcolor.blueF())
                                style.add('BACKGROUND', (c + 1, r + 1), (c + 1, r + 1), cell_color)
                            except Exception:
                                pass
                table.setStyle(style)
                story.append(table)
                if i < len(timetables_data) - 1:
                    story.append(PageBreak())
            doc.build(story)
            QMessageBox.information(self, "Success", f"Successfully exported PDF to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred while creating the PDF:\n{e}")

    def _write_master_timetable_to_pdf(self, file_path, data, h_headers, v_headers):
        try:
            doc = SimpleDocTemplate(file_path, pagesize=landscape(A1))
            styles = getSampleStyleSheet()
            cell_style = styles['Normal']
            cell_style.alignment = 1
            cell_style.fontSize = 6
            cell_style.leading = 7
            story = []
            story.append(Paragraph("Master Teacher Timetable (Staff Deployment)", styles['h1']))
            story.append(Spacer(1, 0.2 * inch))
            table_data = []
            wrapped_h_headers = [Paragraph(h, styles['Normal']) for h in h_headers]
            table_data.append(["Period"] + wrapped_h_headers)
            for i, v_header in enumerate(v_headers):
                row_data = [v_header]
                for cell_text, _ in data[i]:
                    row_data.append(Paragraph(cell_text.replace('\n', '<br/>'), cell_style))
                table_data.append(row_data)
            num_teachers = len(h_headers)
            available_width = 32.1 * inch
            header_col_width = 0.8 * inch
            teacher_col_width = (available_width - header_col_width) / num_teachers
            col_widths = [header_col_width] + [teacher_col_width] * num_teachers
            table = ReportLabTable(table_data, colWidths=col_widths)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (0, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])
            for r in range(len(v_headers)):
                for c in range(len(h_headers)):
                    _, cell_color_hex = data[r][c]
                    if cell_color_hex and cell_color_hex != "#FFFFFF":
                        try:
                            qcolor = QColor(cell_color_hex)
                            cell_color = colors.Color(qcolor.redF(), qcolor.greenF(), qcolor.blueF())
                            style.add('BACKGROUND', (c + 1, r + 1), (c + 1, r + 1), cell_color)
                        except Exception:
                            pass
            table.setStyle(style)
            story.append(table)
            doc.build(story)
            QMessageBox.information(self, "Success", f"Successfully exported Master Timetable to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred while creating the PDF:\n{e}")
            traceback.print_exc()


def setup_database(db_path):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine


def seed_database_if_empty(session):
    # Only select the ID column so it doesn't crash if display_name is missing initially
    if not session.query(ClassSection.id).first():
        print("Database is empty. Seeding...")
        default_sections = ["9th-A", "9th-B", "9th-C", "9th-D", "10th-A", "10th-B", "10th-C", "10th-D"]
        for sec_name in default_sections:
            session.add(ClassSection(name=sec_name, display_name=sec_name, periods_per_day=8))
        session.commit()


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    BASE_DIR = get_base_path()
    DB_PATH = os.path.join(BASE_DIR, "timetable_v5.db")
    SPINNER_PATH = os.path.join(BASE_DIR, "spinner.gif")
    engine = setup_database(DB_PATH)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_database_if_empty(session)
    window = TimetableApp(session, spinner_path=SPINNER_PATH)
    window.show()
    sys.exit(app.exec())