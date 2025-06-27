    def save_to_firestore(self, courses: List[CourseInfo], university_id: str, year: int, semester: int):
        """Save courses to university-specific sub-collection structure"""
        if not self.db:
            print("❌ Firestore not initialized")
            return
        
        # Sub-collection path: UniversityId/courses_year_semester/courseId
        collection_name = f"courses_{year}_{semester}"
        university_ref = self.db.collection(university_id)
        
        # Update university metadata first
        semester_name = {200: "חורף", 201: "אביב", 202: "קיץ"}[semester]
        university_ref.document('metadata').set({
            'last_updated': firestore.SERVER_TIMESTAMP,
            'available_semesters': firestore.ArrayUnion([collection_name]),
            'semester_counts': {
                collection_name: len(courses)
            }
        }, merge=True)
        
        print(f"📝 Updating {university_id} metadata...")
        
        # Save courses to sub-collection
        batch = self.db.batch()
        courses_ref = university_ref.collection(collection_name)
        
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
                batch = self.db.batch()
                print(f"📝 Committed batch {(i + 1) // 500} to {university_id}/{collection_name}")
        
        # Commit remaining documents
        if len(courses) % 500 != 0:
            batch.commit()
        
        print(f"✅ Saved {len(courses)} courses to {university_id}/{collection_name}")
    
    def setup_university_metadata(self, university_id: str):
        """Setup initial university metadata"""
        if not self.db:
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
                }
            }
        }
        
        if university_id in university_configs:
            config = university_configs[university_id]
            self.db.collection(university_id).document('metadata').set(config)
            print(f"✅ Setup metadata for {university_id}")
        else:
            print(f"❌ No configuration found for {university_id}")

# Updated main function usage
def main():
    # ... existing argument parsing ...
    
    # Initialize fetcher
    fetcher = TechnionCourseFetcher(
        cache_dir=args.cache_dir,
        firestore_config=args.firestore_config,
        verbose=args.verbose
    )
    
    # Setup university metadata if needed
    if args.save_firestore:
        fetcher.setup_university_metadata("Technion")
    
    # Fetch courses
    courses = fetcher.fetch_semester_courses(
        year=args.year,
        semester=args.semester,
        output_dir=args.output_dir,
        save_to_firestore=False  # Don't use old method
    )
    
    # Save with new structure
    if args.save_firestore:
        fetcher.save_to_firestore(courses, "Technion", args.year, args.semester)
    
    print(f"🎉 Successfully fetched {len(courses)} courses for Technion!")
