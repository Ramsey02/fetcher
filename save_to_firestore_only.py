#  how to run e.g. python save_to_firestore_only.py --year 2024 --semester 201

import json
import argparse
from smart_fetcher_fixed import save_to_firestore_university_structure, NoCacheTechnionCourseFetcher

# Argument parser
parser = argparse.ArgumentParser(description="Save courses to Firestore for a specific year and semester")
parser.add_argument("--year", type=int, required=True, help="Year, e.g. 2024")
parser.add_argument("--semester", type=int, required=True, help="Semester, e.g. 201")
parser.add_argument("--firestore-config", default="./firebase-config.json", help="Path to Firebase service account JSON")
parser.add_argument("--output-dir", default="./data", help="Output directory for JSON files")
args = parser.parse_args()

# Initialize fetcher (Firestore config required)
fetcher = NoCacheTechnionCourseFetcher(firestore_config=args.firestore_config, verbose=True)

# Load courses from the JSON file
json_path = f"{args.output_dir}/courses_{args.year}_{args.semester}.json"
with open(json_path, encoding="utf-8") as f:
    courses = json.load(f)

# If your JSON contains dicts, but the function expects objects with attributes,
# you may need to convert dicts to objects or update the function to accept dicts.

class CourseObj:
    def __init__(self, d):
        self.course_number = d["general"]["מספר מקצוע"]
        self.name = d["general"].get("שם מקצוע")
        self.syllabus = d["general"].get("סילבוס")
        self.faculty = d["general"].get("פקולטה")
        self.academic_level = d["general"].get("מסגרת לימודים")
        self.points = d["general"].get("נקודות")
        self.responsible = d["general"].get("אחראים")
        self.notes = d["general"].get("הערות")
        self.schedule = d.get("schedule", [])
        self.prerequisites = d["general"].get("מקצועות קדם")
        self.adjoining_courses = d["general"].get("מקצועות צמודים")
        self.no_additional_credit = d["general"].get("מקצועות ללא זיכוי נוסף")
        self.exams = {k: v for k, v in d["general"].items() if "מועד" in k or "בחינה" in k}

# Convert dicts to CourseObj
courses_obj = [CourseObj(c) for c in courses]

# Call the function with the new list
save_to_firestore_university_structure(
    fetcher=fetcher,
    courses=courses_obj,
    university_id="Technion",
    year=args.year,
    semester=args.semester,
    output_dir=args.output_dir
)