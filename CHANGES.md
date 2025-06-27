# Changes from Original technion-sap-info-fetcher

This document outlines the modifications made to the original [technion-sap-info-fetcher](https://github.com/michael-maltsev/technion-sap-info-fetcher) by Michael Maltsev.

## Major Additions
- Firebase/Firestore integration for cloud database storage
- Class-based architecture (`TechnionCourseFetcher` class)
- Automatic semester detection based on current date
- University metadata management system
- Smart fetcher with no-cache option

## Modified Files
- `technion_fetcher_full.py` - Enhanced version of original `courses_to_json.py`
- `smart_fetcher_fixed.py` - New smart fetcher with automatic operation

## New Dependencies
- firebase-admin (for Firestore integration)
- Additional dataclass usage for course information

## Configuration Changes
- Added Firestore configuration support
- Enhanced command-line argument parsing
- Added verbose logging options