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
    
    def get_course_data(self, year: int, semester: int, course_number: str) -> CourseInfo:
        """Get detailed course information"""
        params = {
            "sap-client": "700",
            "$filter": f"Peryr eq '{year}' and Perid eq '{semester}' and Otjid eq '{course_number}'",
            "$select": "Otjid,Points,Name,StudyContentDescription,OrgText,ZzAcademicLevelText,ZzSemesterNote,Responsible,Exams",
            "$expand": "Responsible,Exams",
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
            responsible += f"{person['Title']} {person['FirstName']} {person['LastName']}\n"
        responsible = responsible.rstrip("\n")
        
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
            exams[exam_mapping[category]] = date
        
        return CourseInfo(
            course_number=clean_course_number,
            name=course_data["Name"],
            syllabus=course_data["StudyContentDescription"],
            faculty=course_data["OrgText"],
            academic_level=course_data["ZzAcademicLevelText"],
            points=points,
            responsible=responsible,
            notes=course_data["ZzSemesterNote"],
            exams=exams,
            schedule=[]  # Simplified - no schedule for now
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

def main():
    parser = argparse.ArgumentParser(description="Technion Course Fetcher")
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
    
    print(f"🎉 Successfully fetched {len(courses)} courses!")

if __name__ == "__main__":
    main()
