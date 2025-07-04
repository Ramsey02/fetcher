# Based on technion-sap-info-fetcher by Michael Maltsev
# Original Copyright (C) 2024 Michael Maltsev
# Modified by Ramzy Ayan 2025
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import json
import time
import re
import urllib.parse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import requests
from dataclasses import dataclass
import argparse
from functools import cache

# Firebase imports (install with: pip install firebase-admin)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("Firebase not available. Install with: pip install firebase-admin")

@dataclass
class CourseInfo:
    """Data class for course information"""
    course_number: str
    name: str
    syllabus: str
    faculty: str
    academic_level: str
    points: str
    responsible: str
    prerequisites: str = ""
    adjoining_courses: str = ""
    no_additional_credit: str = ""
    notes: str = ""
    exams: Dict[str, str] = None
    schedule: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.exams is None:
            self.exams = {}
        if self.schedule is None:
            self.schedule = []

class TechnionCourseFetcher:
    """Fetcher for Technion course information with Firestore integration"""
    
    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 firestore_config: Optional[str] = None,
                 verbose: bool = False):
        """Initialize the course fetcher"""
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.verbose = verbose
        self.session = requests.Session()
        
        # Initialize Firestore if config provided
        self.db = None
        if firestore_config and FIREBASE_AVAILABLE:
            self._init_firestore(firestore_config)
        
        # Request headers for Technion SAP API
        self.headers = {
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Brave";v="126"',
            "MaxDataServiceVersion": "2.0",
            "Accept-Language": "he",
            "sec-ch-ua-mobile": "?0",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Content-Type": "multipart/mixed;boundary=batch_1d12-afbf-e3c7",
            "Accept": "multipart/mixed",
            "sap-contextid-accept": "header",
            "sap-cancel-on-close": "true",
            "X-Requested-With": "X",
            "DataServiceVersion": "2.0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-GPC": "1",
            "Origin": "https://portalex.technion.ac.il",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://portalex.technion.ac.il/ovv/",
        }
    
    def _init_firestore(self, config_path: str):
        """Initialize Firestore connection"""
        try:
            cred = credentials.Certificate(config_path)
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("✅ Firestore initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Firestore: {e}")
    
    def _send_request(self, query: str, allow_empty: bool = False) -> Dict[str, Any]:
        """Send request to Technion SAP API with caching"""
        
        # Check cache first
        if self.cache_dir:
            cache_file = self._get_cache_file(query)
            if cache_file.exists():
                with cache_file.open(encoding="utf-8") as f:
                    if self.verbose:
                        print(f"📖 Loading from cache: {query[:50]}...")
                    return json.load(f)
        
        if self.verbose:
            print(f"🌐 Sending request: {query[:50]}...")
        
        url = "https://portalex.technion.ac.il/sap/opu/odata/sap/Z_CM_EV_CDIR_DATA_SRV/$batch?sap-client=700"
        
        data = f"""
--batch_1d12-afbf-e3c7
Content-Type: application/http
Content-Transfer-Encoding: binary

GET {query} HTTP/1.1
sap-cancel-on-close: true
X-Requested-With: X
sap-contextid-accept: header
Accept: application/json
Accept-Language: he
DataServiceVersion: 2.0
MaxDataServiceVersion: 2.0


--batch_1d12-afbf-e3c7--
""".replace("\n", "\r\n")
        
        response = self.session.post(url, headers=self.headers, data=data, timeout=60)
        
        if response.status_code != 202:
            raise RuntimeError(f"Bad status code: {response.status_code}")
        
        response_chunks = response.text.replace("\r\n", "\n").strip().split("\n\n")
        if len(response_chunks) != 3:
            raise RuntimeError(f"Invalid response format")
        
        json_str = response_chunks[2].split("\n", 1)[0]
        result = json.loads(json_str)
        
        if not allow_empty and result == {"d": {"results": []}}:
            raise RuntimeError("Empty response")
        
        # Cache the result
        if self.cache_dir:
            cache_file = self._get_cache_file(query)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        
        return result
    
    def _get_cache_file(self, query: str) -> Path:
        """Generate cache file path for query"""
        cache_name = re.sub(r"[<>:\"/\\|?*]", "_", query)[:64]
        cache_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
        return self.cache_dir / f"{cache_name}_{cache_hash}.json"
    
    def _parse_sap_date(self, date_str: str) -> datetime:
        """Parse SAP date format"""
        match = re.match(r"/Date\((\d+)\)/", date_str)
        if not match:
            raise ValueError(f"Invalid date format: {date_str}")
        return datetime.fromtimestamp(int(match.group(1)) / 1000, timezone.utc)
    
    def get_semesters(self) -> List[Dict[str, Any]]:
        """Get available semesters"""
        params = {
            "sap-client": "700",
            "$select": "PiqYear,PiqSession,Begda,Endda",
        }
        query = f"SemesterSet?{urllib.parse.urlencode(params)}"
        raw_data = self._send_request(query)
        
        semesters = []
        for result in raw_data["d"]["results"]:
            year = int(result["PiqYear"])
            semester = int(result["PiqSession"])
            
            if semester not in [200, 201, 202]:  # Winter, Spring, Summer
                continue
            
            start_date = self._parse_sap_date(result["Begda"]).strftime("%Y-%m-%d")
            end_date = self._parse_sap_date(result["Endda"]).strftime("%Y-%m-%d")
            
            semesters.append({
                "year": year,
                "semester": semester,
                "start_date": start_date,
                "end_date": end_date,
                "semester_code": f"{year}-{semester}"
            })
        
        return sorted(semesters, key=lambda x: (x["year"], x["semester"]), reverse=True)
    
    def get_course_numbers(self, year: int, semester: int) -> List[str]:
        """Get all course numbers for a semester"""
        params = {
            "sap-client": "700",
            "$skip": "0",
            "$top": "10000",
            "$filter": f"Peryr eq '{year}' and Perid eq '{semester}'",
            "$select": "Otjid",
        }
        query = f"SmObjectSet?{urllib.parse.urlencode(params)}"
        raw_data = self._send_request(query)
        return [x["Otjid"] for x in raw_data["d"]["results"]]
    
    @cache
    def get_building_name(self, year: int, semester: int, room_id: str):
        """Get building name from room ID"""
        if not room_id:
            return ""
        
        params = {"sap-client": "700", "$select": "Building"}
        query = f"GObjectSet(Otjid='{urllib.parse.quote(room_id)}',Peryr='{year}',Perid='{semester}')?{urllib.parse.urlencode(params)}"
        
        try:
            raw_data = self._send_request(query)
            building = raw_data["d"]["Building"]
            if building:
                building = re.sub(r"\s+", " ", building.strip())
                # Apply building name mappings
                building_mapping = {
                    "בנין אולמן": "אולמן",
                    "בנין בורוביץ הנדסה אזרחית": "בורוביץ הנדסה אזרחית",
                    "בנין דן קהאן": "דן קהאן",
                    "בנין הנ' אוירונאוטית": "הנ' אוירונאוטית",
                    "בנין זיסאפל": "זיסאפל",
                    "בנין להנדסת חמרים": "הנדסת חמרים",
                    "בנין ליידי דייוס": "ליידי דייוס",
                    "בנין למדעי המחשב": "מדעי המחשב",
                    "בנין ע'ש אמדו": "אמדו",
                    "בנין ע'ש טאוב": "טאוב",
                    "בנין ע'ש סגו": "סגו",
                    "בנין פישבך": "פישבך",
                    "בנין פקולטה לרפואה": "פקולטה לרפואה",
                    "בניין ננו-אלקטרוניקה": "ננו-אלקטרוניקה",
                    "בניין ספורט": "ספורט",
                }
                for old, new in building_mapping.items():
                    if building.startswith(old):
                        return new + building[len(old):]
                return building
        except Exception:
            pass
        
        return ""
    
    def _parse_schedule_text(self, schedule_text: str) -> List[tuple]:
        """Parse schedule text into day/time entries"""
        # Clean up the schedule text
        schedule_text = re.sub(r"^מ \d\d\.\d\d\., ", "", schedule_text)
        schedule_text = re.sub(r"^עד \d\d\.\d\d\., ", "", schedule_text)
        schedule_text = re.sub(r"^\d\d\.\d\d\. עד \d\d\.\d\d\., ", "", schedule_text)
        schedule_text = re.sub(r", יוצא מן הכלל: .*$", "", schedule_text)
        schedule_text = re.sub(r", הכל \d+ ימים$", "", schedule_text)
        
        entries = []
        for entry in schedule_text.split(","):
            entry = entry.strip()
            
            match = re.match(
                r"(?:יום|יוֹם) (רִאשׁוֹ|ראשון|שני|שלישי|רביעי|חמישי|שישי) (\d\d:\d\d)\s*-\s*(\d\d:\d\d)",
                entry
            )
            if match:
                day = match.group(1)
                if day == "רִאשׁוֹ":
                    day = "ראשון"
                time_begin = match.group(2)
                time_end = match.group(3)
                entries.append((day, time_begin, time_end))
        
        return entries
    
    def get_course_schedule(self, year: int, semester: int, course_number: str) -> List[Dict[str, Any]]:
        """Get course schedule information"""
        params = {
            "sap-client": "700",
            "$expand": "EObjectSet,EObjectSet/Persons",
        }
        query = f"SmObjectSet(Otjid='SM{course_number}',Peryr='{year}',Perid='{semester}',ZzCgOtjid='',ZzPoVersion='',ZzScOtjid='')/SeObjectSet?{urllib.parse.urlencode(params)}"
        
        try:
            raw_data = self._send_request(query, allow_empty=True)
        except RuntimeError:
            return []
        
        schedule_results = raw_data["d"]["results"]
        if not schedule_results:
            return []
        
        schedule = []
        
        def raw_schedule_sort_key(raw_schedule):
            # Sort by group id in ascending order, but place 0 groups at the end.
            group_id = int(raw_schedule["ZzSeSeqnr"])
            return group_id == 0, group_id
        
        for raw_schedule in sorted(schedule_results, key=raw_schedule_sort_key):
            group_id = int(raw_schedule["ZzSeSeqnr"])
            
            for raw_item in raw_schedule["EObjectSet"]["results"]:
                category = raw_item["CategoryText"]
                
                # Handle special cases for sport courses
                is_sport_course = re.match(r"03940[89]\d\d", course_number) is not None
                if is_sport_course:
                    if category in ["ספורט", "נבחרת ספורט"]:
                        category = raw_item["Name"]
                        if (re.match(r"ספורט חינוך גופני\s*-", category) or 
                            category == "ספורט נבחרות ספורט"):
                            if raw_schedule["Name"]:
                                category = re.sub(r"^SE\d+\s*", "", raw_schedule["Name"])
                elif category not in ["הרצאה", "תרגול", "מעבדה", "פרויקט", "סמינר"]:
                    # Skip unknown categories or handle them
                    if category:
                        pass  # Keep the original category
                
                # Extract room information
                building = ""
                room = 0
                building_room_dict = None
                room_text = raw_item.get("RoomText", "")
                
                if room_text and room_text != "ראה פרטים":
                    room_match = re.match(r"(\d\d\d)-(\d\d\d\d)", room_text)
                    if room_match:
                        building = self.get_building_name(year, semester, raw_item.get("RoomId", ""))
                        room = int(room_match.group(2))
                elif room_text == "ראה פרטים" or not room_text:
                    # Try to get room information from EventScheduleSet
                    event_id = raw_item.get("Otjid", "")
                    if event_id:
                        building_room_dict = self.get_room_info(year, semester, event_id)
                        if self.verbose and building_room_dict:
                            print(f"📍 Found room info via EventScheduleSet for {event_id}: {len(building_room_dict)} time slots")
                else:
                    # Try to get room info from event schedule
                    event_schedule_id = raw_item.get("Otjid", "").replace("SM", "")
                    room_info = self.get_room_info(year, semester, event_schedule_id)
                    if room_info:
                        (building, room) = list(room_info.values())[0]
                
                # Extract staff information
                staff = ""
                for person in raw_item["Persons"]["results"]:
                    title = person["Title"].strip()
                    if title and title != "-":
                        staff += f"{title} "
                    staff += f"{person['FirstName']} {person['LastName']}\n"
                staff = staff.rstrip("\n")
                
                # Parse schedule text
                schedule_text = raw_item.get("ScheduleSummary", "")
                if not schedule_text or schedule_text == "לֹא סָדִיר":
                    continue
                
                # Skip specific dates
                if (re.match(r"\d\d\.\d\d\.: \d\d:\d\d-\d\d:\d\d", schedule_text) or 
                    re.match(r"(\d\d\.\d\d\., )+בהתאמה \d\d:\d\d-\d\d:\d\d", schedule_text)):
                    continue
                
                # Parse day and time
                day_time_entries = self._parse_schedule_text(schedule_text)
                
                for day, time_begin, time_end in day_time_entries:
                    # Use building_room_dict if available (for cases where RoomText was empty or "ראה פרטים")
                    final_building = building
                    final_room = room
                    
                    if building_room_dict:
                        # Map Hebrew day names to weekday numbers (0=Sunday in the original code)
                        day_mapping = {
                            "ראשון": 0,
                            "שני": 1, 
                            "שלישי": 2,
                            "רביעי": 3,
                            "חמישי": 4,
                            "שישי": 5
                        }
                        weekday = day_mapping.get(day, -1)
                        if weekday != -1:
                            weekday_and_time = (weekday, time_begin, time_end)
                            if weekday_and_time in building_room_dict:
                                final_building, final_room = building_room_dict[weekday_and_time]
                                if self.verbose:
                                    print(f"📍 Using room info from EventScheduleSet: {final_building}-{final_room}")
                    
                    schedule.append({
                        "קבוצה": group_id,
                        "סוג": category,
                        "יום": day,
                        "שעה": f"{time_begin} - {time_end}",
                        "בניין": final_building,
                        "חדר": final_room,
                        "מרצה/מתרגל": staff,
                        "מס.": int(raw_item["Otjid"]) if raw_item["Otjid"].isdigit() else group_id
                    })
        
        return schedule
    
    def _extract_prerequisites(self, prereq_data: List[Dict]) -> str:
        """Extract prerequisites from SAP data"""
        prereq = ""
        for item in prereq_data:
            prereq += item["Bracket"]
            if item["ModuleId"].lstrip("0"):
                prereq += item["ModuleId"]
            if item["Operator"] == "AND":
                prereq += " ו-"
            elif item["Operator"] == "OR":
                prereq += " או "
        
        # Clean up parentheses
        prereq = re.sub(r"\((\d+)\)", r"\1", prereq)
        prereq = re.sub(r"^\(([^()]+)\)$", r"\1", prereq)
        return prereq.strip()
    
    def _extract_relations(self, relations_data: List[Dict]) -> str:
        """Extract course relations (no additional credit)"""
        relations = []
        
        for item in relations_data:
            course_num = item["Otjid"].removeprefix("SM")
            if item["ZzRelationshipKey"] in ["AZEC", "AZID"]:
                relations.append(course_num)
        
        return " ".join(relations)
    
    def _extract_adjoining_courses(self, semester_notes: str) -> List[str]:
        """Extract adjoining courses from semester notes"""
        if not semester_notes:
            return []
        
        parts = re.split(
            r"^(?:מקצוע צמוד|מקצועות צמודים):",
            semester_notes,
            maxsplit=1,
            flags=re.MULTILINE,
        )
        
        if len(parts) == 1:
            return []
        
        content = parts[1].strip()
        courses = []
        
        # Try to extract course numbers
        if match := re.match(r"\d{5,8}(\s*,\s*\d{5,8})*$", content, flags=re.MULTILINE):
            courses = [x.strip() for x in match.group(0).split(",")]
        elif match := re.match(r"(.*?)(?:\.$|\.\n|\n\n|$)", content, flags=re.DOTALL):
            for adjoining_course in match.group(1).split(","):
                adjoining_course = adjoining_course.strip()
                match = re.match(r"(\d{5,8})(\s.*)?", adjoining_course)
                if match:
                    courses.append(match.group(1))
        
        # Normalize course numbers
        result = []
        for course in courses:
            if len(course) <= 6:
                course = course.zfill(6)
                # Convert old format to new format if needed
                if re.match(r"^9730\d\d$", course):
                    course = "970300" + course[4:]
                elif re.match(r"^\d{3}\d{3}$", course):
                    course = "0" + course[:3] + "0" + course[3:]
            else:
                course = course.zfill(8)
            result.append(course)
        
        return result
    
    def get_course_data(self, year: int, semester: int, course_number: str) -> CourseInfo:
        """Get detailed course information"""
        params = {
            "sap-client": "700",
            "$filter": f"Peryr eq '{year}' and Perid eq '{semester}' and Otjid eq '{course_number}'",
            "$select": "Otjid,Points,Name,StudyContentDescription,OrgText,ZzAcademicLevelText,ZzSemesterNote,Responsible,Exams,SmRelations,SmPrereq",
            "$expand": "Responsible,Exams,SmRelations,SmPrereq",
        }
        query = f"SmObjectSet?{urllib.parse.urlencode(params)}"
        raw_data = self._send_request(query)
        
        results = raw_data["d"]["results"]
        if len(results) != 1:
            raise RuntimeError(f"Expected 1 result for {course_number}, got {len(results)}")
        
        course_data = results[0]
        
        # Extract course number without SM prefix
        clean_course_number = course_data["Otjid"]
        if clean_course_number.startswith("SM"):
            clean_course_number = clean_course_number[2:]
        
        # Format points
        points = course_data["Points"]
        points = re.sub(r"(\.[1-9]+)0+$", r"\1", points)
        points = re.sub(r"\.0+$", r"", points)
        
        # Extract responsible staff
        responsible = ""
        for person in course_data["Responsible"]["results"]:
            title = person["Title"].strip()
            if title and title != "-":
                responsible += f"{title} "
            responsible += f"{person['FirstName']} {person['LastName']}\n"
        responsible = responsible.rstrip("\n")
        
        # Extract prerequisites
        prereq = self._extract_prerequisites(course_data["SmPrereq"]["results"])
        
        # Extract relations (no additional credit)
        relations = self._extract_relations(course_data["SmRelations"]["results"])
        
        # Extract adjoining courses
        adjoining = self._extract_adjoining_courses(course_data["ZzSemesterNote"])
        
        # Process exams
        exams = {}
        exam_mapping = {
            "FI": "מועד א",
            "FB": "מועד ב", 
            "MI": "בוחן מועד א",
            "M2": "בוחן מועד ב"
        }
        
        for exam in course_data["Exams"]["results"]:
            category = exam.get("CategoryCode")
            if category not in exam_mapping:
                continue
            
            date_raw = exam.get("ExamDate")
            if not date_raw:
                continue
            
            date = self._parse_sap_date(date_raw).strftime("%d-%m-%Y")
            
            # Extract time if available
            time_begin_raw = exam.get("ExamBegTime", "")
            time_end_raw = exam.get("ExamEndTime", "")
            
            time_str = ""
            if time_begin_raw and time_end_raw:
                begin_match = re.match(r"PT(\d\d)H(\d\d)M\d\dS", time_begin_raw)
                end_match = re.match(r"PT(\d\d)H(\d\d)M\d\dS", time_end_raw)
                
                if begin_match and end_match:
                    time_begin = f"{begin_match.group(1)}:{begin_match.group(2)}"
                    time_end = f"{end_match.group(1)}:{end_match.group(2)}"
                    if time_begin != "00:00" or time_end != "00:00":
                        time_str = f" {time_begin} - {time_end}"
            
            exams[exam_mapping[category]] = f"{date}{time_str}"
        
        # Get schedule
        schedule = self.get_course_schedule(year, semester, clean_course_number)
        
        return CourseInfo(
            course_number=clean_course_number,
            name=course_data["Name"],
            syllabus=course_data["StudyContentDescription"],
            faculty=course_data["OrgText"],
            academic_level=course_data["ZzAcademicLevelText"],
            points=points,
            responsible=responsible,
            prerequisites=prereq,
            adjoining_courses=" ".join(adjoining) if adjoining else "",
            no_additional_credit=relations,
            notes=course_data["ZzSemesterNote"],
            exams=exams,
            schedule=schedule
        )
    
    def save_to_json(self, courses: List[CourseInfo], file_path: str):
        """Save courses to JSON file"""
        courses_data = []
        for course in courses:
            course_dict = {
                "general": {
                    "מספר מקצוע": course.course_number,
                    "שם מקצוע": course.name,
                    "סילבוס": course.syllabus,
                    "פקולטה": course.faculty,
                    "מסגרת לימודים": course.academic_level,
                    "נקודות": course.points,
                    "אחראים": course.responsible,
                    "הערות": course.notes,
                },
                "schedule": course.schedule
            }
            
            # Add optional fields
            if course.prerequisites:
                course_dict["general"]["מקצועות קדם"] = course.prerequisites
            if course.adjoining_courses:
                course_dict["general"]["מקצועות צמודים"] = course.adjoining_courses
            if course.no_additional_credit:
                course_dict["general"]["מקצועות ללא זיכוי נוסף"] = course.no_additional_credit
            
            # Add exam information
            for exam_type, exam_date in course.exams.items():
                if exam_date:
                    course_dict["general"][exam_type] = exam_date
            
            courses_data.append(course_dict)
        
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(courses_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {len(courses_data)} courses to {file_path}")
    
    def save_to_firestore(self, courses: List[CourseInfo], year: int, semester: int):
        """Save courses to Firestore"""
        if not self.db:
            print("❌ Firestore not initialized")
            return
        
        collection_name = f"courses_{year}_{semester}"
        batch = self.db.batch()
        
        for i, course in enumerate(courses):
            doc_ref = self.db.collection(collection_name).document(course.course_number)
            
            course_data = {
                "courseNumber": course.course_number,
                "name": course.name,
                "syllabus": course.syllabus,
                "faculty": course.faculty,
                "academicLevel": course.academic_level,
                "points": course.points,
                "responsible": course.responsible,
                "prerequisites": course.prerequisites,
                "adjoiningCourses": course.adjoining_courses,
                "noAdditionalCredit": course.no_additional_credit,
                "notes": course.notes,
                "exams": course.exams,
                "schedule": course.schedule,
                "lastUpdated": firestore.SERVER_TIMESTAMP,
                "year": year,
                "semester": semester
            }
            
            batch.set(doc_ref, course_data)
            
            # Commit in batches of 500 (Firestore limit)
            if (i + 1) % 500 == 0:
                batch.commit()
                batch = self.db.batch()
                print(f"📝 Committed batch {(i + 1) // 500}")
        
        # Commit remaining documents
        if len(courses) % 500 != 0:
            batch.commit()
        
        print(f"✅ Saved {len(courses)} courses to Firestore collection: {collection_name}")
    
    def fetch_semester_courses(self, 
                              year: int, 
                              semester: int,
                              output_dir: Optional[str] = None,
                              save_to_firestore: bool = False) -> List[CourseInfo]:
        """Fetch all courses for a specific semester"""
        print(f"🔍 Fetching courses for {year}-{semester}...")
        
        course_numbers = self.get_course_numbers(year, semester)
        print(f"📚 Found {len(course_numbers)} courses")
        
        courses = []
        failed_courses = []
        
        for i, course_number in enumerate(course_numbers, 1):
            try:
                if self.verbose:
                    print(f"[{i}/{len(course_numbers)}] Fetching {course_number}")
                else:
                    if i % 10 == 0:
                        print(f"📖 Processed {i}/{len(course_numbers)} courses")
                
                course = self.get_course_data(year, semester, course_number)
                courses.append(course)
                
                # Small delay to be respectful to the server
                time.sleep(0.1)
                
            except Exception as e:
                failed_courses.append(course_number)
                if self.verbose:
                    print(f"❌ Failed to fetch {course_number}: {e}")
        
        if failed_courses:
            print(f"⚠️  Failed to fetch {len(failed_courses)} courses")
        
        # Save to local file
        if output_dir:
            filename = f"courses_{year}_{semester}.json"
            filepath = Path(output_dir) / filename
            self.save_to_json(courses, str(filepath))
        
        # Save to Firestore
        if save_to_firestore:
            self.save_to_firestore(courses, year, semester)
        
        return courses
    
    def get_room_info(self, year: int, semester: int, event_schedule_id: str) -> Dict[tuple, tuple]:
        """Get room information for a specific event schedule ID"""
        params = {
            "sap-client": "700",
            "$filter": (
                f"Otjid eq '{event_schedule_id}' and Peryr eq '{year}' and Perid eq"
                f" '{semester}'"
            ),
            "$expand": "Rooms",
        }
        
        try:
            raw_data = self._send_request(f"EventScheduleSet?{urllib.parse.urlencode(params)}")
            results = raw_data["d"]["results"]
            
            rooms_by_time = {}
            
            for result in results:
                date_raw = result.get("Evdat", "")
                begin_raw = result.get("Beguz", "")
                end_raw = result.get("Enduz", "")
                
                if not date_raw or not begin_raw or not end_raw:
                    continue
                
                # Parse date
                date = self._sap_date_parse(date_raw)
                weekday = (date.weekday() + 1) % 7  # Convert to 0=Sunday format
                
                # Parse begin time
                begin_match = re.fullmatch(r"PT(\d\d)H(\d\d)M00S", begin_raw)
                if not begin_match:
                    continue
                begin_time = f"{begin_match.group(1)}:{begin_match.group(2)}"
                
                # Parse end time
                end_match = re.fullmatch(r"PT(\d\d)H(\d\d)M00S", end_raw)
                if not end_match:
                    continue
                end_time = f"{end_match.group(1)}:{end_match.group(2)}"
                
                weekday_and_time = (weekday, begin_time, end_time)
                
                # Process rooms
                rooms = result.get("Rooms", {}).get("results", [])
                
                buildings = set()
                room_numbers = set()
                
                for room in rooms:
                    room_id = room.get("Otjid", "")
                    room_name = room.get("Name", "")
                    
                    # Match room format like "123-4567"
                    room_match = re.fullmatch(r"(\d\d\d)-(\d\d\d\d)", room_name)
                    if room_match:
                        building = self.get_building_name(year, semester, room_id)
                        room_number = int(room_match.group(2))
                        buildings.add(building)
                        room_numbers.add(room_number)
                
                if len(buildings) == 1:
                    building = buildings.pop()
                    room_number = room_numbers.pop() if len(room_numbers) == 1 else 0
                    rooms_by_time[weekday_and_time] = (building, room_number)
                    
            return rooms_by_time
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to get room info for {event_schedule_id}: {e}")
            return {}
    
    def _sap_date_parse(self, date_str: str) -> datetime:
        """Parse SAP date format /Date(timestamp)/"""
        match = re.fullmatch(r"/Date\((\d+)\)/", date_str)
        if not match:
            raise RuntimeError(f"Invalid date: {date_str}")
        return datetime.fromtimestamp(int(match.group(1)) / 1000, timezone.utc)

    # ...existing code...
def main():
    parser = argparse.ArgumentParser(description="Technion Course Fetcher with Full Schedule Support")
    parser.add_argument("--year", type=int, help="Academic year (e.g., 2024)")
    parser.add_argument("--semester", type=int, help="Semester code (200=Winter, 201=Spring, 202=Summer)")
    parser.add_argument("--output-dir", default="./courses_data", help="Output directory for JSON files")
    parser.add_argument("--cache-dir", default="./.cache", help="Cache directory")
    parser.add_argument("--firestore-config", help="Path to Firebase service account JSON")
    parser.add_argument("--save-firestore", action="store_true", help="Save to Firestore")
    parser.add_argument("--list-semesters", action="store_true", help="List available semesters")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Initialize fetcher
    fetcher = TechnionCourseFetcher(
        cache_dir=args.cache_dir,
        firestore_config=args.firestore_config,
        verbose=args.verbose
    )
    
    if args.list_semesters:
        print("📅 Available semesters:")
        semesters = fetcher.get_semesters()
        for sem in semesters[:10]:  # Show last 10 semesters
            semester_name = {200: "Winter", 201: "Spring", 202: "Summer"}[sem["semester"]]
            print(f"  {sem['year']}-{sem['semester']} ({semester_name} {sem['year']})")
        return
    
    if not args.year or not args.semester:
        print("❌ Please specify --year and --semester, or use --list-semesters to see available options")
        return
    
    # Fetch courses
    courses = fetcher.fetch_semester_courses(
        year=args.year,
        semester=args.semester,
        output_dir=args.output_dir,
        save_to_firestore=args.save_firestore
    )
    
    print(f"🎉 Successfully fetched {len(courses)} courses with complete schedule data!")

if __name__ == "__main__":
    main()
