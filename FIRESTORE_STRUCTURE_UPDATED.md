# Updated Firestore Structure - University-Centric Approach

## Database Structure

### Root Collections (Universities)
```
Technion/
├── metadata/                        # Document with university info
│   ├── name: "Technion Israel Institute of Technology"
│   ├── name_en: "Technion"
│   ├── name_he: "הטכניון"
│   ├── country: "Israel"
│   ├── city: "Haifa"
│   ├── website: "https://technion.ac.il"
│   ├── logo_url: "https://..."
│   ├── established: 1912
│   ├── semester_system: "200/201/202"
│   ├── semester_names: {
│   │   "200": "חורף",
│   │   "201": "אביב", 
│   │   "202": "קיץ"
│   ├── }
│   ├── available_years: [2023, 2024, 2025]
│   ├── total_courses: 1500
│   ├── last_updated: timestamp
│   └── fetcher_config: {
│       "api_type": "sap",
│       "base_url": "https://portalex.technion.ac.il/...",
│       "update_frequency": "daily"
│   }
├── courses_2024_200/               # Sub-collection (Winter 2024)
│   ├── 02340124/                   # Course document
│   │   ├── general: {...}
│   │   ├── schedule: [...]
│   │   └── metadata: {
│   │       "fetched_at": timestamp,
│   │       "source": "technion_sap"
│   │   }
│   └── 02340117/
├── courses_2024_201/               # Sub-collection (Spring 2024)
├── courses_2024_202/               # Sub-collection (Summer 2024)
└── courses_2025_200/               # Sub-collection (Winter 2025)

HUJI/
├── metadata/
│   ├── name: "Hebrew University of Jerusalem"
│   ├── name_he: "האוניברסיטה העברית"
│   └── semester_system: "fall/spring"
├── courses_2024_fall/
└── courses_2024_spring/

TAU/
├── metadata/
│   ├── name: "Tel Aviv University"
│   └── ...
└── courses_2024_201/
```

## Flutter Integration

### University Service
```dart
class UniversityService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  // Get university metadata
  Future<University> getUniversity(String universityId) async {
    final doc = await _firestore
        .collection(universityId)
        .doc('metadata')
        .get();
    
    return University.fromJson(doc.data()!);
  }

  // Get available semesters for university
  Future<List<String>> getAvailableSemesters(String universityId) async {
    final collections = await _firestore
        .collection(universityId)
        .listCollections();
    
    return collections
        .map((c) => c.id)
        .where((id) => id.startsWith('courses_'))
        .toList();
  }

  // Get courses for specific semester
  Stream<List<Course>> getCourses(String universityId, String semester) {
    return _firestore
        .collection(universityId)
        .collection(semester)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => Course.fromJson(doc.data()))
            .toList());
  }

  // Search courses across university
  Stream<List<Course>> searchCourses(String universityId, String query) {
    // Can search within specific semesters or use collection group queries
    return _firestore
        .collectionGroup('courses_2024_201') // Specific semester
        .where('name', arrayContains: query)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => Course.fromJson(doc.data()))
            .toList());
  }
}
```

### Course Service (Updated)
```dart
class CourseService {
  final UniversityService _universityService = UniversityService();

  // Get courses for current semester of user's university
  Stream<List<Course>> getCurrentCourses(String userId) async* {
    final user = await getUserProfile(userId);
    final university = user.university;
    final currentSemester = getCurrentSemester();
    
    yield* _universityService.getCourses(university, currentSemester);
  }
}
```

## Querying Patterns

### Single University Queries (Most Common)
```dart
// Get all courses for Technion Spring 2024
db.collection('Technion')
  .collection('courses_2024_201')
  .get()

// Search within university
db.collection('Technion')
  .collection('courses_2024_201')
  .where('general.פקולטה', '==', 'מדעי המחשב')
  .get()
```

### Cross-University Queries (When Needed)
```dart
// Compare same course across universities
db.collectionGroup('courses_2024_201')
  .where('general.מספר מקצוע', '==', '02340124')
  .get()
```

## Updated Fetcher Code

```python
def save_to_firestore(self, courses, university_id, year, semester):
    """Save courses to university-specific sub-collection"""
    
    if not self.db:
        print("❌ Firestore not initialized")
        return
    
    # Sub-collection path: University/courses_year_semester/courseId
    collection_name = f"courses_{year}_{semester}"
    university_ref = self.db.collection(university_id)
    
    # Update university metadata
    university_ref.document('metadata').set({
        'last_updated': firestore.SERVER_TIMESTAMP,
        'available_semesters': firestore.ArrayUnion([collection_name])
    }, merge=True)
    
    # Save courses to sub-collection
    batch = self.db.batch()
    courses_ref = university_ref.collection(collection_name)
    
    for i, course in enumerate(courses):
        doc_ref = courses_ref.document(course.course_number)
        course_data = {
            "general": {...},
            "schedule": course.schedule,
            "metadata": {
                "fetched_at": firestore.SERVER_TIMESTAMP,
                "university": university_id,
                "year": year,
                "semester": semester
            }
        }
        
        batch.set(doc_ref, course_data)
        
        if (i + 1) % 500 == 0:
            batch.commit()
            batch = self.db.batch()
    
    if len(courses) % 500 != 0:
        batch.commit()
    
    print(f"✅ Saved {len(courses)} courses to {university_id}/{collection_name}")

# Usage
fetcher.save_to_firestore(courses, "Technion", 2024, 201)
```

## Benefits of This Structure

### 🎯 **Organization:**
- Clean university namespaces
- Logical data hierarchy
- Easy to understand and maintain

### ⚡ **Performance:**
- Sub-collections are efficient for this use case
- Most queries are university-specific anyway
- Can still do cross-university queries when needed

### 🚀 **Scalability:**
- Easy to add new universities
- University-specific permissions
- Independent data management

### 💼 **Business Value:**
- Clear data ownership per university
- University-specific features/customization
- Partnership opportunities

This structure is perfect for your multi-university vision! 🎯
