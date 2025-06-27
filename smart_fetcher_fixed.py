import datetime
import argparse
import sys
import json
import requests
from pathlib import Path
from technion_fetcher_full import TechnionCourseFetcher

class NoCacheTechnionCourseFetcher(TechnionCourseFetcher):
    """Technion Course Fetcher that always fetches from API (no caching)"""
    
    def __init__(self, 
                 cache_dir=None,  # Ignore cache_dir
                 firestore_config=None,
                 verbose=False):
        """Initialize the course fetcher without caching"""
        super().__init__(cache_dir=None, firestore_config=firestore_config, verbose=verbose)
        # Force disable caching by setting cache_dir to None
        self.cache_dir = None
        if verbose:
            print("🚫 Caching disabled - all requests will fetch from API")
    
    def _send_request(self, query, allow_empty=False):
        """Send request to Technion SAP API WITHOUT caching"""
        
        if self.verbose:
            print(f"🌐 Fetching from API (no cache): {query[:50]}...")
        
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
        
        # NO CACHING - just return the result directly
        if self.verbose:
            print(f"✅ Fresh data fetched from API")
        
        return result

def get_current_semester():
    """Automatically determine current semester based on date"""
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    
    # Technion semester system (approximate):
    # Winter (200): October - February
    # Spring (201): March - July  
    # Summer (202): July - September
    
    if month >= 10 or month <= 2:
        # Winter semester
        semester_year = year if month >= 10 else year
        return semester_year, 200
    elif month >= 3 and month <= 7:
        # Spring semester
        return year, 201
    else:
        # Summer semester
        return year, 202

def get_next_semester(year, semester):
    """Get the next semester"""
    if semester == 200:  # Winter -> Spring
        return year, 201
    elif semester == 201:  # Spring -> Summer
        return year, 202
    else:  # Summer -> Next Winter
        return year + 1, 200

def setup_university_metadata(fetcher, university_id="Technion"):
    """Setup initial university metadata"""
    if not fetcher.db:
        print("❌ Firestore not initialized")
        return
        
    university_configs = {
        "Technion": {
            "name": "Israel Institute of Technology",
            "name_en": "Technion",
            "name_he": "הטכניון",
            "country": "Israel", 
            "city": "Haifa",
            "website": "https://technion.ac.il",
            "established": 1912,
            "semester_system": "200/201/202",
            "semester_names": {
                "200": "חורף",
                "201": "אביב", 
                "202": "קיץ"
            },
            "logo_url": "https://upload.wikimedia.org/wikipedia/en/thumb/8/81/Technion_Israel_Institute_of_Technology_logo.svg/1200px-Technion_Israel_Institute_of_Technology_logo.svg.png",
            "fetcher_config": {
                "api_type": "sap",
                "base_url": "https://portalex.technion.ac.il",
                "update_frequency": "daily"
            },
            "last_updated": datetime.datetime.now().isoformat()
        }
    }
    
    if university_id in university_configs:
        config = university_configs[university_id]
        fetcher.db.collection(university_id).document('metadata').set(config)
        print(f"✅ Setup metadata for {university_id}")
    else:
        print(f"❌ No configuration found for {university_id}")

def save_to_firestore_university_structure(fetcher, courses, university_id, year, semester):
    """Save courses to university-specific sub-collection structure"""
    if not fetcher.db:
        print("❌ Firestore not initialized")
        return
    
    from firebase_admin import firestore
    
    # FIXED: Create proper Firestore structure
    # Collections > Documents > Sub-collections
    collection_name = f"courses_{year}_{semester}"
    
    # Reference the university collection
    university_collection = fetcher.db.collection(university_id)
    
    # Update university metadata (this creates a document)
    semester_name = {200: "חורף", 201: "אביב", 202: "קיץ"}[semester]
    university_collection.document('metadata').set({
        'last_updated': firestore.SERVER_TIMESTAMP,
        'available_semesters': firestore.ArrayUnion([collection_name]),
        f'semester_counts.{collection_name}': len(courses)
    }, merge=True)
    
    print(f"📝 Updating {university_id} metadata...")
    
    # FIXED: Create courses as a sub-collection under the university document
    # Structure: University (collection) > data (document) > courses_YYYY_SSS (sub-collection)
    university_doc = university_collection.document('data')
    courses_ref = university_doc.collection(collection_name)
    
    # Create batch for efficient writes
    batch = fetcher.db.batch()
    
    for i, course in enumerate(courses):
        doc_ref = courses_ref.document(course.course_number)
        
        course_data = {
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
            "schedule": course.schedule,
            "metadata": {
                "fetched_at": firestore.SERVER_TIMESTAMP,
                "university": university_id,
                "year": year,
                "semester": semester,
                "semester_name": semester_name
            }
        }
        
        # Add optional fields
        if course.prerequisites:
            course_data["general"]["מקצועות קדם"] = course.prerequisites
        if course.adjoining_courses:
            course_data["general"]["מקצועות צמודים"] = course.adjoining_courses
        if course.no_additional_credit:
            course_data["general"]["מקצועות ללא זיכוי נוסף"] = course.no_additional_credit
        
        # Add exam information
        for exam_type, exam_date in course.exams.items():
            if exam_date:
                course_data["general"][exam_type] = exam_date
        
        batch.set(doc_ref, course_data)
        
        # Commit in batches of 500 (Firestore limit)
        if (i + 1) % 500 == 0:
            batch.commit()
            batch = fetcher.db.batch()
            print(f"📝 Committed batch {(i + 1) // 500} to {university_id}/data/{collection_name}")
    
    # Commit remaining documents
    if len(courses) % 500 != 0:
        batch.commit()
    
    print(f"✅ Saved {len(courses)} courses to {university_id}/data/{collection_name}")

def main():
    parser = argparse.ArgumentParser(description="Smart Technion Course Fetcher (No Cache)")
    parser.add_argument("--cache-dir", default="./.cache", help="Cache directory (IGNORED - no caching)")
    parser.add_argument("--firestore-config", help="Path to Firebase service account JSON")
    parser.add_argument("--output-dir", default="./data", help="Output directory for JSON files")
    parser.add_argument("--current-only", action="store_true", help="Only fetch current semester")
    parser.add_argument("--force-year", type=int, help="Force specific year")
    parser.add_argument("--force-semester", type=int, help="Force specific semester")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-cache", action="store_true", default=True, help="Disable caching (always enabled)")
    
    args = parser.parse_args()
    
    print("🤖 Smart Technion Course Fetcher (NO CACHE)")
    print("=" * 50)
    print("🚫 Caching is DISABLED - all data will be fetched fresh from API")
    
    # Initialize fetcher with NO CACHE
    fetcher = NoCacheTechnionCourseFetcher(
        firestore_config=args.firestore_config,
        verbose=args.verbose
    )
    
    if not fetcher.db:
        print("❌ Firestore not initialized. Please provide --firestore-config")
        sys.exit(1)
    
    # Setup university metadata
    setup_university_metadata(fetcher, "Technion")
    
    # Determine semesters to fetch
    if args.force_year and args.force_semester:
        current_year, current_semester = args.force_year, args.force_semester
        semesters_to_fetch = [(current_year, current_semester)]
    else:
        current_year, current_semester = get_current_semester()
        semesters_to_fetch = [(current_year, current_semester)]
        
        if not args.current_only:
            next_year, next_semester = get_next_semester(current_year, current_semester)
            semesters_to_fetch.append((next_year, next_semester))
    
    successful_fetches = 0
    failed_fetches = 0
    
    for year, semester in semesters_to_fetch:
        semester_name = {200: "Winter", 201: "Spring", 202: "Summer"}[semester]
        print(f"\n🔍 Fetching {semester_name} {year} ({year}-{semester}) - FRESH FROM API")
        
        try:
            # Fetch courses
            courses = fetcher.fetch_semester_courses(
                year=year,
                semester=semester,
                output_dir=args.output_dir
            )
            
            if not courses:
                print(f"⚠️ No courses found for {year}-{semester}")
                continue
            
            # Save to Firestore with university structure
            save_to_firestore_university_structure(fetcher, courses, "Technion", year, semester)
            
            print(f"✅ Successfully updated {semester_name} {year}: {len(courses)} courses")
            successful_fetches += 1
            
        except Exception as e:
            print(f"❌ Failed to fetch {semester_name} {year}: {e}")
            failed_fetches += 1
            
            # Don't exit on failure - try next semester
            continue
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"✅ Successful: {successful_fetches}")
    print(f"❌ Failed: {failed_fetches}")
    print(f"🚫 All data was fetched fresh from API (no cache used)")
    
    if failed_fetches > 0 and successful_fetches == 0:
        print("🚨 All fetches failed!")
        sys.exit(1)
    elif failed_fetches > 0:
        print("⚠️ Some fetches failed, but continuing...")
        sys.exit(0)
    else:
        print("🎉 All fetches completed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
