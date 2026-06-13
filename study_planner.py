#!/usr/bin/env python3
"""
Smart Study Planner CLI
A terminal-based study planner application written in Python.
Uses only Python Standard Libraries.

Features:
- Add subjects and topics with difficulty levels (Easy, Medium, Hard).
- Set exam dates and input daily available study hours.
- Automatic study schedule generation prioritizing subjects with nearest deadlines.
- Interactive terminal menus with input validation.
- JSON-based persistent storage.
- Study streak tracking.
- Colorized terminal output using ANSI escape codes.
"""

import json
import os
import re
from datetime import datetime, date

# ---------------------------------------------------------
# ANSI TERMINAL COLORS CONFIGURATION
# ---------------------------------------------------------

# Try to initialize Windows terminal virtual terminal processing for ANSI escape sequences
try:
    if os.name == 'nt':
        os.system('')
except Exception:
    pass

class Colors:
    """ANSI color codes for terminal text formatting."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def colorize(text, color_code):
    """Wraps text in ANSI escape codes."""
    return f"{color_code}{text}{Colors.ENDC}"

# ---------------------------------------------------------
# FORMATTING UTILITIES (STANDARD LIBRARY ONLY)
# ---------------------------------------------------------

def ansi_len(text):
    """Calculates the display length of a string, ignoring ANSI escape sequences."""
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mG]')
    return len(ansi_escape.sub('', text))

def pad_cell(text, width, align='left'):
    """Pads a cell to a fixed width while maintaining correct alignment with ANSI colors."""
    text_str = str(text)
    plain_len = ansi_len(text_str)
    padding = max(0, width - plain_len)
    
    if align == 'right':
        return ' ' * padding + text_str
    elif align == 'center':
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + text_str + ' ' * right_pad
    else:
        return text_str + ' ' * padding

def print_table(headers, rows, alignments=None):
    """
    Prints a formatted ASCII table.
    alignments: List of alignment strings ('left', 'right', 'center') for each column.
    """
    if not rows:
        print(colorize("No data to display in table.", Colors.WARNING))
        return

    if not alignments:
        alignments = ['left'] * len(headers)
    
    # Calculate column widths based on maximum display width in each column
    col_widths = [ansi_len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], ansi_len(str(cell)))
            
    # Form horizontal lines
    border_line = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    
    # Print table header
    print(border_line)
    header_row = "| " + " | ".join([
        pad_cell(colorize(str(h), Colors.BOLD + Colors.CYAN), col_widths[i], alignments[i]) 
        for i, h in enumerate(headers)
    ]) + " |"
    print(header_row)
    print(border_line)
    
    # Print table rows
    for row in rows:
        row_cells = []
        for i, cell in enumerate(row):
            row_cells.append(pad_cell(cell, col_widths[i], alignments[i]))
        print("| " + " | ".join(row_cells) + " |")
        
    print(border_line)

# ---------------------------------------------------------
# DOMAIN MODELS
# ---------------------------------------------------------

class Topic:
    """Represents a topic within a subject."""
    
    DIFFICULTY_WEIGHTS = {
        'Easy': 1.0,
        'Medium': 2.0,
        'Hard': 3.0
    }
    
    def __init__(self, name, difficulty='Medium', completed=False):
        self.name = name
        self.difficulty = difficulty if difficulty in self.DIFFICULTY_WEIGHTS else 'Medium'
        self.completed = completed
        
    @property
    def weight(self):
        """Returns the study weight (effort estimation in hours) for this topic."""
        return self.DIFFICULTY_WEIGHTS[self.difficulty]
        
    def to_dict(self):
        """Serializes the Topic to a dictionary."""
        return {
            'name': self.name,
            'difficulty': self.difficulty,
            'completed': self.completed
        }
        
    @staticmethod
    def from_dict(d):
        """Deserializes a Topic from a dictionary."""
        return Topic(
            name=d.get('name', 'Unnamed Topic'),
            difficulty=d.get('difficulty', 'Medium'),
            completed=d.get('completed', False)
        )


class Subject:
    """Represents a subject/course containing multiple topics."""
    
    def __init__(self, name, exam_date):
        self.name = name
        self.exam_date = exam_date  # Expects datetime.date object
        self.topics = []
        
    def get_progress(self):
        """Returns completion progress percentage for this subject."""
        if not self.topics:
            return 100.0
        completed_count = sum(1 for t in self.topics if t.completed)
        return (completed_count / len(self.topics)) * 100
        
    def get_incomplete_topics(self):
        """Returns a list of all incomplete topics."""
        return [t for t in self.topics if not t.completed]
        
    def to_dict(self):
        """Serializes the Subject to a dictionary."""
        return {
            'name': self.name,
            'exam_date': self.exam_date.strftime("%Y-%m-%d"),
            'topics': [t.to_dict() for t in self.topics]
        }
        
    @staticmethod
    def from_dict(d):
        """Deserializes a Subject from a dictionary."""
        exam_date_obj = datetime.strptime(d.get('exam_date'), "%Y-%m-%d").date()
        subject = Subject(name=d.get('name', 'Unnamed Subject'), exam_date=exam_date_obj)
        subject.topics = [Topic.from_dict(t) for t in d.get('topics', [])]
        return subject


class StudyPlanner:
    """Manages subjects, daily study hours, streaks, and handles storage & logic."""
    
    def __init__(self, data_file="study_planner_data.json"):
        self.data_file = data_file
        self.subjects = []
        self.daily_study_hours = 2.0  # Default value
        self.streak = 0
        self.last_completion_date = None
        
    def add_subject(self, name, exam_date):
        """Creates and adds a new subject to the planner."""
        # Check if subject already exists
        for s in self.subjects:
            if s.name.lower() == name.lower():
                return False, "Subject already exists."
        
        subject = Subject(name, exam_date)
        self.subjects.append(subject)
        self.save_data()
        return True, f"Subject '{name}' added successfully."
        
    def add_topic_to_subject(self, subject_name, topic_name, difficulty):
        """Adds a topic to a specific subject."""
        subject = self.find_subject(subject_name)
        if not subject:
            return False, "Subject not found."
            
        # Check if topic already exists in this subject
        for t in subject.topics:
            if t.name.lower() == topic_name.lower():
                return False, f"Topic '{topic_name}' already exists under '{subject.name}'."
                
        topic = Topic(topic_name, difficulty)
        subject.topics.append(topic)
        self.save_data()
        return True, f"Topic '{topic_name}' ({difficulty}) added to '{subject.name}'."
        
    def find_subject(self, subject_name):
        """Utility method to find a subject by name (case-insensitive)."""
        for s in self.subjects:
            if s.name.lower() == subject_name.lower():
                return s
        return None
        
    def mark_topic_completed(self, subject_name, topic_name):
        """Marks a topic as completed and updates the study streak."""
        subject = self.find_subject(subject_name)
        if not subject:
            return False, "Subject not found."
            
        topic = None
        for t in subject.topics:
            if t.name.lower() == topic_name.lower():
                topic = t
                break
                
        if not topic:
            return False, "Topic not found."
            
        if topic.completed:
            return True, f"Topic '{topic.name}' is already completed."
            
        topic.completed = True
        
        # Streak tracking logic
        today_dt = date.today()
        streak_msg = ""
        
        if self.last_completion_date is None:
            self.streak = 1
            self.last_completion_date = today_dt
            streak_msg = "First study session logged! Streak started at 1 day! 🔥"
        elif self.last_completion_date == today_dt:
            # Already completed a topic today, streak doesn't change
            streak_msg = f"Keep up the good work! Current streak: {self.streak} days. 🔥"
        elif (today_dt - self.last_completion_date).days == 1:
            self.streak += 1
            self.last_completion_date = today_dt
            streak_msg = f"Awesome! Streak increased to {self.streak} days! 🔥"
        else:
            self.streak = 1
            self.last_completion_date = today_dt
            streak_msg = "Streak reset, but you're back on track! Streak: 1 day. 🔥"
            
        self.save_data()
        return True, f"Marked '{topic.name}' as completed!\n{streak_msg}"
        
    def check_streak_validity(self):
        """Resets the streak if the last completed task was before yesterday."""
        if self.last_completion_date is None:
            self.streak = 0
            return
            
        today_dt = date.today()
        days_diff = (today_dt - self.last_completion_date).days
        if days_diff > 1:
            self.streak = 0
            
    def generate_daily_schedule(self):
        """
        Generates a study schedule prioritizing subjects with the nearest deadlines.
        """
        today_dt = date.today()
        active_subjects = []
        
        for s in self.subjects:
            days_left = (s.exam_date - today_dt).days
            incomplete_topics = s.get_incomplete_topics()
            
            # Schedule subjects with incomplete topics and exams in the future or today
            if incomplete_topics:
                active_subjects.append({
                    'subject': s,
                    'days_left': days_left,
                    'incomplete': incomplete_topics
                })
                
        # Sort: nearest deadlines first. If deadlines tie, sort by total remaining workload weight descending
        active_subjects.sort(key=lambda x: (x['days_left'], -sum(t.weight for t in x['incomplete'])))
        
        table_rows = []
        next_topics = {}
        total_required_hours = 0.0
        remaining_available_hours = self.daily_study_hours
        
        for item in active_subjects:
            s = item['subject']
            days_left = item['days_left']
            incomplete = item['incomplete']
            
            total_weight = sum(t.weight for t in incomplete)
            
            # Determine how many days are left to study. If today is exam day or overdue, count as 1 to avoid ZeroDivisionError
            study_days = max(1, days_left)
            required_hours_per_day = total_weight / study_days
            total_required_hours += required_hours_per_day
            
            # Allocation based on available hours and priority order
            allocated = min(required_hours_per_day, remaining_available_hours)
            remaining_available_hours = max(0.0, remaining_available_hours - allocated)
            
            # Format days left string
            if days_left < 0:
                days_str = colorize(f"Overdue ({abs(days_left)}d)", Colors.FAIL)
            elif days_left == 0:
                days_str = colorize("TODAY!", Colors.WARNING + Colors.BOLD)
            elif days_left <= 3:
                days_str = colorize(f"{days_left} days", Colors.WARNING + Colors.BOLD)
            else:
                days_str = colorize(f"{days_left} days", Colors.GREEN)
                
            # Formatting hours
            req_hours_str = f"{required_hours_per_day:.2f} hrs"
            alloc_hours_str = f"{allocated:.2f} hrs"
            if allocated > 0:
                alloc_hours_str = colorize(alloc_hours_str, Colors.GREEN + Colors.BOLD)
            else:
                alloc_hours_str = colorize(alloc_hours_str, Colors.FAIL)
                
            table_rows.append([
                colorize(s.name, Colors.BOLD),
                days_str,
                f"{len(incomplete)} / {len(s.topics)}",
                f"{total_weight:.1f} hrs",
                req_hours_str,
                alloc_hours_str
            ])
            
            # Recommend next topics sorted by difficulty weight descending (Hardest first)
            sorted_incomplete = sorted(incomplete, key=lambda x: -x.weight)
            next_topics[s.name] = sorted_incomplete[:2]  # Recommend top 2 focus topics
            
        warning_msg = None
        if total_required_hours > self.daily_study_hours and active_subjects:
            warning_msg = (
                f"⚠️  {colorize('Warning', Colors.WARNING + Colors.BOLD)}: The total daily study hours required to meet "
                f"all deadlines ({total_required_hours:.2f} hrs/day) exceeds your daily available limit "
                f"({self.daily_study_hours:.2f} hrs/day).\n"
                f"The schedule below has prioritized subjects with the nearest deadlines."
            )
            
        return table_rows, next_topics, total_required_hours, warning_msg

    # ---------------------------------------------------------
    # JSON DATA PERSISTENCE
    # ---------------------------------------------------------
    
    def save_data(self):
        """Saves current planner state to the JSON file."""
        try:
            data = {
                'daily_study_hours': self.daily_study_hours,
                'streak': self.streak,
                'last_completion_date': self.last_completion_date.strftime("%Y-%m-%d") if self.last_completion_date else None,
                'subjects': [s.to_dict() for s in self.subjects]
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(colorize(f"Error saving data: {e}", Colors.FAIL))
            
    def load_data(self):
        """Loads planner state from the JSON file."""
        if not os.path.exists(self.data_file):
            return
            
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.daily_study_hours = data.get('daily_study_hours', 2.0)
            self.streak = data.get('streak', 0)
            
            last_date_str = data.get('last_completion_date')
            if last_date_str:
                self.last_completion_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            else:
                self.last_completion_date = None
                
            self.subjects = [Subject.from_dict(s) for s in data.get('subjects', [])]
            self.check_streak_validity()
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(colorize(f"Warning: Failed to load previous study data correctly ({e}). Starting fresh.", Colors.WARNING))

# ---------------------------------------------------------
# CLI VALDIATION HELPERS
# ---------------------------------------------------------

def prompt_non_empty(prompt_text):
    """Loops until user enters a non-empty string."""
    while True:
        val = input(prompt_text).strip()
        if val:
            return val
        print(colorize("Input cannot be empty. Please try again.", Colors.FAIL))

def prompt_date(prompt_text):
    """Loops until user enters a valid date in YYYY-MM-DD format."""
    while True:
        val = input(prompt_text).strip()
        try:
            parsed_date = datetime.strptime(val, "%Y-%m-%d").date()
            return parsed_date
        except ValueError:
            print(colorize("Invalid format! Use YYYY-MM-DD (e.g. 2026-06-30).", Colors.FAIL))

def prompt_float(prompt_text, min_val=0.1, max_val=24.0):
    """Loops until user enters a valid float within range."""
    while True:
        val = input(prompt_text).strip()
        try:
            f_val = float(val)
            if min_val <= f_val <= max_val:
                return f_val
            print(colorize(f"Value must be between {min_val} and {max_val}.", Colors.FAIL))
        except ValueError:
            print(colorize("Invalid number! Please enter a valid decimal number.", Colors.FAIL))

def prompt_difficulty():
    """Prompts and returns a difficulty level."""
    while True:
        print("\nSelect Difficulty:")
        print("1. Easy   (Weight: 1.0 hr)")
        print("2. Medium (Weight: 2.0 hrs)")
        print("3. Hard   (Weight: 3.0 hrs)")
        choice = input("Enter choice (1-3) [Default: 2]: ").strip()
        
        if choice == "" or choice == "2":
            return "Medium"
        elif choice == "1":
            return "Easy"
        elif choice == "3":
            return "Hard"
        else:
            print(colorize("Invalid choice. Selecting Medium by default.", Colors.WARNING))
            return "Medium"

# ---------------------------------------------------------
# INTERACTIVE MENUS & MAIN LOOP
# ---------------------------------------------------------

def print_header(planner):
    """Prints a styled CLI application header, containing the study streak."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(colorize("           📚 SMART STUDY PLANNER CLI 📚", Colors.HEADER + Colors.BOLD))
    print("=" * 60)
    
    # Render Streak banner
    if planner.streak > 0:
        streak_banner = f"🔥 Active Streak: {planner.streak} Day" + ("s" if planner.streak > 1 else "") + " 🔥"
        print(colorize(streak_banner.center(60), Colors.WARNING + Colors.BOLD))
    else:
        print(colorize("No active streak yet. Complete a topic to start one! 🚀".center(60), Colors.BLUE))
        
    print(f"Daily Available Study Hours: {planner.daily_study_hours:.1f} hrs")
    print("=" * 60)

def main():
    planner = StudyPlanner()
    planner.load_data()
    
    while True:
        print_header(planner)
        print("1. " + colorize("Add Subject & Topics", Colors.BOLD))
        print("2. View Subjects & Completion Progress")
        print("3. Generate Daily Study Schedule")
        print("4. Mark Topic as Completed")
        print("5. View Study Statistics")
        print("6. Update Daily Study Hours Limit")
        print("7. " + colorize("Exit", Colors.FAIL))
        print("-" * 60)
        
        choice = input("Enter menu choice (1-7): ").strip()
        
        try:
            if choice == '1':
                # ADD SUBJECT
                print(colorize("\n--- Add New Subject ---", Colors.CYAN + Colors.BOLD))
                sub_name = prompt_non_empty("Enter subject name: ")
                exam_date_val = prompt_date("Enter exam date (YYYY-MM-DD): ")
                
                success, msg = planner.add_subject(sub_name, exam_date_val)
                if not success:
                    print(colorize(msg, Colors.FAIL))
                    input("\nPress Enter to return to menu...")
                    continue
                    
                print(colorize(msg, Colors.GREEN))
                
                # Add topics loop
                add_topics = input("\nWould you like to add study topics/chapters for this subject? (y/n) [y]: ").strip().lower()
                if add_topics == '' or add_topics == 'y' or add_topics == 'yes':
                    while True:
                        print(colorize(f"\n--- Adding topic to {sub_name} ---", Colors.BLUE))
                        top_name = prompt_non_empty("Enter topic name: ")
                        diff = prompt_difficulty()
                        
                        t_success, t_msg = planner.add_topic_to_subject(sub_name, top_name, diff)
                        if t_success:
                            print(colorize(t_msg, Colors.GREEN))
                        else:
                            print(colorize(t_msg, Colors.FAIL))
                            
                        another = input("\nAdd another topic to this subject? (y/n) [y]: ").strip().lower()
                        if another == 'n' or another == 'no':
                            break
                input("\nPress Enter to return to menu...")
                
            elif choice == '2':
                # VIEW SUBJECTS
                print(colorize("\n--- Subjects List & Progress ---", Colors.CYAN + Colors.BOLD))
                if not planner.subjects:
                    print("No subjects registered yet. Choose option 1 to add a subject.")
                else:
                    today_dt = date.today()
                    rows = []
                    for s in planner.subjects:
                        days_left = (s.exam_date - today_dt).days
                        progress = s.get_progress()
                        
                        # Progress string formatting with color
                        prog_str = f"{progress:.1f}%"
                        if progress == 100.0:
                            prog_str = colorize(prog_str, Colors.GREEN + Colors.BOLD)
                            status = colorize("Completed", Colors.GREEN)
                        elif days_left < 0:
                            status = colorize("Overdue", Colors.FAIL)
                        elif days_left <= 3:
                            status = colorize("Urgent", Colors.WARNING + Colors.BOLD)
                        else:
                            status = colorize("In Progress", Colors.BLUE)
                            
                        # Exam date color formatting
                        if days_left < 0:
                            days_str = colorize(f"Overdue ({abs(days_left)} days ago)", Colors.FAIL)
                        elif days_left == 0:
                            days_str = colorize("TODAY!", Colors.WARNING + Colors.BOLD)
                        else:
                            days_str = f"{days_left} days left"
                            
                        # Format row
                        rows.append([
                            colorize(s.name, Colors.BOLD),
                            s.exam_date.strftime("%Y-%m-%d"),
                            days_str,
                            f"{sum(1 for t in s.topics if t.completed)} / {len(s.topics)}",
                            prog_str,
                            status
                        ])
                        
                    headers = ["Subject", "Exam Date", "Days Remaining", "Topics Comp/Total", "Progress", "Status"]
                    aligns = ["left", "center", "center", "center", "right", "center"]
                    print_table(headers, rows, aligns)
                    
                    # Detailed breakdown
                    detail = input("\nWould you like to view detailed topics for a specific subject? (y/n) [n]: ").strip().lower()
                    if detail == 'y' or detail == 'yes':
                        print("\nSelect subject:")
                        for idx, s in enumerate(planner.subjects, 1):
                            print(f"{idx}. {s.name}")
                        sub_choice = input(f"Enter choice (1-{len(planner.subjects)}): ").strip()
                        try:
                            sub_idx = int(sub_choice) - 1
                            if 0 <= sub_idx < len(planner.subjects):
                                target_sub = planner.subjects[sub_idx]
                                print(colorize(f"\n--- Topics for {target_sub.name} ---", Colors.BLUE + Colors.BOLD))
                                if not target_sub.topics:
                                    print("No topics added to this subject yet.")
                                else:
                                    t_rows = []
                                    for t in target_sub.topics:
                                        t_status = colorize("✓ Completed", Colors.GREEN) if t.completed else colorize("✗ Pending", Colors.FAIL)
                                        
                                        diff_str = t.difficulty
                                        if t.difficulty == "Easy":
                                            diff_str = colorize(diff_str, Colors.GREEN)
                                        elif t.difficulty == "Medium":
                                            diff_str = colorize(diff_str, Colors.WARNING)
                                        elif t.difficulty == "Hard":
                                            diff_str = colorize(diff_str, Colors.FAIL + Colors.BOLD)
                                            
                                        t_rows.append([
                                            t.name,
                                            diff_str,
                                            f"{t.weight:.1f} hrs",
                                            t_status
                                        ])
                                    t_headers = ["Topic Name", "Difficulty", "Est. Hours", "Status"]
                                    t_aligns = ["left", "center", "center", "center"]
                                    print_table(t_headers, t_rows, t_aligns)
                            else:
                                print(colorize("Invalid subject selection.", Colors.FAIL))
                        except ValueError:
                            print(colorize("Invalid input. Must be a number.", Colors.FAIL))
                input("\nPress Enter to return to menu...")
                
            elif choice == '3':
                # GENERATE DAILY STUDY PLAN
                print(colorize("\n--- Generated Daily Study Schedule ---", Colors.CYAN + Colors.BOLD))
                if not planner.subjects:
                    print("No subjects added. Add subjects and topics first to generate a plan.")
                else:
                    rows, next_topics, total_req, warning = planner.generate_daily_schedule()
                    if not rows:
                        print(colorize("Hooray! No study plan needed because all subjects are 100% completed! 🎉", Colors.GREEN + Colors.BOLD))
                    else:
                        if warning:
                            print(warning + "\n")
                            
                        headers = ["Subject", "Days Left", "Topics Left/Total", "Est. Effort", "Req. Study/Day", "Allocated Daily Study"]
                        aligns = ["left", "center", "center", "center", "right", "right"]
                        print_table(headers, rows, aligns)
                        
                        # Display specific target topics
                        print(colorize("\n📌 Recommended Focus Areas for Today:", Colors.CYAN + Colors.BOLD))
                        has_focus_areas = False
                        for subj_name, topics in next_topics.items():
                            # Only show focus areas if user has time allocated or is overdue
                            # Check row allocation for this subject to see if study time > 0
                            subj_allocated = 0.0
                            for r in rows:
                                if subj_name in r[0]:  # match colored name
                                    # extract number from colored string
                                    clean_r = ansi_len(r[5]) # test width or search
                                    # Find matching float value
                                    match = re.search(r'\d+\.\d+', r[5])
                                    if match:
                                        subj_allocated = float(match.group())
                                    break
                            
                            if subj_allocated > 0 and topics:
                                has_focus_areas = True
                                print(f"\n🔹 {colorize(subj_name, Colors.BOLD)} (Focus: {subj_allocated:.2f} hrs):")
                                for t in topics:
                                    diff_display = t.difficulty
                                    if t.difficulty == 'Easy':
                                        diff_display = colorize(t.difficulty, Colors.GREEN)
                                    elif t.difficulty == 'Medium':
                                        diff_display = colorize(t.difficulty, Colors.WARNING)
                                    else:
                                        diff_display = colorize(t.difficulty, Colors.FAIL + Colors.BOLD)
                                        
                                    print(f"  • {t.name} [{diff_display}] - Est. {t.weight:.1f} hrs")
                        
                        if not has_focus_areas:
                            print("No focus areas. Daily available study hours limit is too low to allocate time today.")
                input("\nPress Enter to return to menu...")
                
            elif choice == '4':
                # MARK TOPIC COMPLETED
                print(colorize("\n--- Mark Topic as Completed ---", Colors.CYAN + Colors.BOLD))
                
                # Filter subjects that have incomplete topics
                active_subs = [s for s in planner.subjects if s.get_incomplete_topics()]
                
                if not active_subs:
                    print("All registered subjects and topics are fully completed! Nothing to mark.")
                else:
                    print("Select subject:")
                    for idx, s in enumerate(active_subs, 1):
                        print(f"{idx}. {s.name} ({len(s.get_incomplete_topics())} topics remaining)")
                        
                    sub_choice = input(f"Enter choice (1-{len(active_subs)}): ").strip()
                    try:
                        sub_idx = int(sub_choice) - 1
                        if 0 <= sub_idx < len(active_subs):
                            target_sub = active_subs[sub_idx]
                            incomplete_topics = target_sub.get_incomplete_topics()
                            
                            print(f"\nSelect topic from {target_sub.name} to complete:")
                            for idx, t in enumerate(incomplete_topics, 1):
                                print(f"{idx}. {t.name} [{t.difficulty}]")
                                
                            top_choice = input(f"Enter choice (1-{len(incomplete_topics)}): ").strip()
                            top_idx = int(top_choice) - 1
                            if 0 <= top_idx < len(incomplete_topics):
                                target_topic = incomplete_topics[top_idx]
                                
                                success, msg = planner.mark_topic_completed(target_sub.name, target_topic.name)
                                if success:
                                    print(colorize("\n" + msg, Colors.GREEN + Colors.BOLD))
                                else:
                                    print(colorize("\n" + msg, Colors.FAIL))
                            else:
                                print(colorize("Invalid topic selection.", Colors.FAIL))
                        else:
                            print(colorize("Invalid subject selection.", Colors.FAIL))
                    except ValueError:
                        print(colorize("Invalid input. Must be a number.", Colors.FAIL))
                input("\nPress Enter to return to menu...")
                
            elif choice == '5':
                # VIEW STATISTICS
                print(colorize("\n--- Study Performance & Stats ---", Colors.CYAN + Colors.BOLD))
                if not planner.subjects:
                    print("No subjects added. Add subjects to view stats.")
                else:
                    total_subjects = len(planner.subjects)
                    total_topics = sum(len(s.topics) for s in planner.subjects)
                    completed_topics = sum(sum(1 for t in s.topics if t.completed) for s in planner.subjects)
                    
                    overall_progress = (completed_count := completed_topics) / (total_count := max(1, total_topics)) * 100
                    
                    # Difficulty counts of remaining topics
                    diff_counts = {'Easy': 0, 'Medium': 0, 'Hard': 0}
                    for s in planner.subjects:
                        for t in s.get_incomplete_topics():
                            if t.difficulty in diff_counts:
                                diff_counts[t.difficulty] += 1
                                
                    print(f"• Total Subjects: {total_subjects}")
                    print(f"• Total Topics: {total_topics}")
                    print(f"• Completed Topics: {completed_topics}")
                    print(f"• Pending Topics: {total_topics - completed_topics}")
                    
                    # Highlight streak
                    streak_color = Colors.GREEN if planner.streak > 0 else Colors.BLUE
                    print(f"• Current Streak: {colorize(f'{planner.streak} Days', streak_color + Colors.BOLD)}")
                    
                    # Progress Bar
                    bar_length = 30
                    filled_length = int(round(bar_length * overall_progress / 100))
                    bar = '█' * filled_length + '-' * (bar_length - filled_length)
                    progress_bar_str = colorize(f"|{bar}| {overall_progress:.1f}%", Colors.GREEN if overall_progress == 100.0 else Colors.BLUE)
                    print(f"• Overall Progress: {progress_bar_str}")
                    
                    print(colorize("\nDifficulty Breakdown of Remaining Topics:", Colors.CYAN))
                    print(f"  🟢 Easy:   {diff_counts['Easy']}")
                    print(f"  🟡 Medium: {diff_counts['Medium']}")
                    print(f"  🔴 Hard:   {diff_counts['Hard']}")
                input("\nPress Enter to return to menu...")
                
            elif choice == '6':
                # UPDATE STUDY HOURS LIMIT
                print(colorize("\n--- Update Daily Study Limit ---", Colors.CYAN + Colors.BOLD))
                print(f"Current Limit: {planner.daily_study_hours:.1f} hours/day")
                new_hours = prompt_float("Enter new daily available study hours (0.1 - 24.0): ")
                planner.daily_study_hours = new_hours
                planner.save_data()
                print(colorize(f"Daily study hours limit updated to {new_hours:.1f} hours/day.", Colors.GREEN))
                input("\nPress Enter to return to menu...")
                
            elif choice == '7':
                # EXIT
                planner.save_data()
                print(colorize("\nThank you for using Smart Study Planner. Keep learning and good luck with your exams! 🎓🚀", Colors.GREEN + Colors.BOLD))
                break
            else:
                print(colorize("Invalid menu option! Please select a choice between 1 and 7.", Colors.FAIL))
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            # Handle user typing Ctrl+C gracefully
            print(colorize("\n\nOperation cancelled. Returning to main menu.", Colors.WARNING))
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
