# GitHub Actions Workflow for Automatic Course Fetching
# File: .github/workflows/fetch-courses.yml

name: Fetch Technion Courses

on:
  schedule:
    # Run daily at 2 AM UTC (5 AM Israel time)
    - cron: '0 2 * * *'
  
  # Allow manual triggering
  workflow_dispatch:

jobs:
  fetch-courses:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r fetcher/requirements.txt
    
    - name: Create Firebase config
      run: |
        echo '${{ secrets.FIREBASE_CONFIG }}' > fetcher/firebase-config.json
    
    - name: Fetch current semester courses
      run: |
        cd fetcher
        python technion_fetcher_full.py --year 2024 --semester 201 --firestore-config ./firebase-config.json --save-firestore --verbose
    
    - name: Fetch next semester courses (if available)
      run: |
        cd fetcher
        python technion_fetcher_full.py --year 2024 --semester 202 --firestore-config ./firebase-config.json --save-firestore --verbose
      continue-on-error: true  # Don't fail if semester doesn't exist yet
    
    - name: Clean up
      run: rm -f fetcher/firebase-config.json

---

# Smart Fetcher Script that detects current semester
# File: fetcher/smart_fetch.py

import datetime
from technion_fetcher_full import TechnionCourseFetcher

def get_current_semester():
    """Automatically determine current semester based on date"""
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    
    # Technion semester system:
    # Winter (200): October - February
    # Spring (201): March - July  
    # Summer (202): July - September
    
    if month >= 10 or month <= 2:
        # Winter semester
        semester_year = year if month >= 10 else year - 1
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

def main():
    fetcher = TechnionCourseFetcher(
        cache_dir="./.cache",
        firestore_config="./firebase-config.json",
        verbose=True
    )
    
    # Setup university metadata
    fetcher.setup_university_metadata("Technion")
    
    # Get current and next semester
    current_year, current_semester = get_current_semester()
    next_year, next_semester = get_next_semester(current_year, current_semester)
    
    print(f"🔍 Fetching current semester: {current_year}-{current_semester}")
    
    try:
        # Fetch current semester
        courses = fetcher.fetch_semester_courses(
            year=current_year,
            semester=current_semester,
            output_dir="./data"
        )
        
        fetcher.save_to_firestore(courses, "Technion", current_year, current_semester)
        print(f"✅ Updated current semester: {len(courses)} courses")
        
    except Exception as e:
        print(f"❌ Failed to fetch current semester: {e}")
    
    print(f"🔍 Fetching next semester: {next_year}-{next_semester}")
    
    try:
        # Fetch next semester (if available)
        next_courses = fetcher.fetch_semester_courses(
            year=next_year,
            semester=next_semester,
            output_dir="./data"
        )
        
        fetcher.save_to_firestore(next_courses, "Technion", next_year, next_semester)
        print(f"✅ Updated next semester: {len(next_courses)} courses")
        
    except Exception as e:
        print(f"⚠️ Next semester not yet available: {e}")

if __name__ == "__main__":
    main()

---

# Updated GitHub Action using smart fetcher
# File: .github/workflows/smart-fetch.yml

name: Smart Course Fetcher

on:
  schedule:
    # Run twice daily: 2 AM and 2 PM UTC
    - cron: '0 2,14 * * *'
  workflow_dispatch:

jobs:
  smart-fetch:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: pip install -r fetcher/requirements.txt
    
    - name: Create Firebase config
      run: echo '${{ secrets.FIREBASE_CONFIG }}' > fetcher/firebase-config.json
    
    - name: Run smart fetcher
      run: |
        cd fetcher
        python smart_fetch.py
    
    - name: Notify on failure
      if: failure()
      run: |
        echo "Fetcher failed! Check logs."
        # Add notification logic (email, Slack, etc.)

---

# Setup Instructions

## 1. Add Firebase Config to GitHub Secrets

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Add new secret: `FIREBASE_CONFIG`
3. Paste your entire firebase-config.json content as the value

## 2. Enable GitHub Actions

1. Commit these files to your repo
2. GitHub Actions will run automatically on schedule
3. Check the "Actions" tab to monitor runs

## 3. Manual Triggers

You can manually trigger fetching:
- Go to Actions tab
- Select the workflow
- Click "Run workflow"

## Benefits of GitHub Actions

✅ **FREE** - 2,000 minutes/month for public repos
✅ **Reliable** - Runs on GitHub's infrastructure  
✅ **Easy setup** - Just commit YAML files
✅ **Monitoring** - Built-in logs and notifications
✅ **Flexible** - Easy to modify schedules
✅ **Secure** - Secrets management built-in
