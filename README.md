## Attribution

This project is a derivative work based on [technion-sap-info-fetcher](https://github.com/michael-maltsev/technion-sap-info-fetcher) by Michael Maltsev, licensed under GPL-3.0.

### Original Work
- **Author**: Michael Maltsev
- **Copyright**: (C) 2024 Michael Maltsev
- **License**: GNU General Public License v3.0
- **Repository**: https://github.com/michael-maltsev/technion-sap-info-fetcher
- **Purpose**: A script to fetch and parse Technion SAP courses information in accessible JSON format
- **Original Features**: 
  - SAP API integration for Technion course data
  - Course schedule parsing and formatting
  - Building name mapping and room information
  - Exam date extraction and formatting
  - Prerequisite and course relationship parsing
  - Caching system for API responses

### Relationship to Original Work
This project extends and enhances the original technion-sap-info-fetcher while maintaining full compatibility with its core functionality. The original parsing logic, API endpoints, and data structures serve as the foundation for all enhancements made in this version.

### Enhancements Made
#### 🔥 **Firebase Integration**
- Full Firestore database integration for cloud storage
- Real-time course data synchronization
- University-specific collection structure
- Automatic metadata management
- Batch upload optimization for large datasets

#### 🏗️ **Architecture Improvements**
- Restructured as object-oriented class-based architecture
- `TechnionCourseFetcher` base class with extensible design
- `NoCacheTechnionCourseFetcher` for real-time data fetching
- Modular design supporting multiple universities
- Enhanced error handling and recovery mechanisms

#### 🤖 **Smart Automation**
- Automatic current semester detection based on date
- Next semester prediction and pre-fetching
- University metadata setup and management
- Intelligent batch processing with progress tracking
- Configurable update frequency and scheduling

#### 📊 **Data Management**
- Enhanced course data validation
- Improved schedule conflict detection
- Extended metadata fields for course tracking
- Better handling of Hebrew text and encoding
- Structured university information storage

#### 🛠️ **Developer Experience**
- Comprehensive command-line interface
- Verbose logging and debugging options
- Smart caching controls (cache/no-cache modes)
- Better error messages and troubleshooting
- Improved documentation and code comments

#### 🚀 **Performance & Reliability**
- Optimized API request handling
- Better timeout and retry mechanisms
- Memory-efficient batch processing
- Reduced API load through intelligent caching
- Enhanced data consistency checks

### Technical Contributions
- **New Dependencies**: firebase-admin, enhanced dataclass usage
- **Configuration System**: Firebase service account integration
- **Data Models**: CourseInfo dataclass with extended fields
- **CLI Enhancements**: Advanced argument parsing and validation
- **Error Handling**: Comprehensive exception management
- **Logging**: Structured logging with multiple verbosity levels

### Compatibility
This enhanced version maintains full backward compatibility with the original project's:
- JSON output format
- Command-line interface patterns  
- Core data structures and field names
- API interaction methods

### Acknowledgments
Special thanks to Michael Maltsev for creating the original technion-sap-info-fetcher and making it available under GPL-3.0. This project builds upon their excellent foundation work in reverse-engineering the Technion SAP API and creating robust parsing algorithms.

The original project's comprehensive approach to handling Hebrew text, complex schedule parsing, and SAP API quirks provided an invaluable starting point for these enhancements.

### Contributing
As this is a GPL-3.0 licensed derivative work, all contributions must also be licensed under GPL-3.0. Contributors should:
- Acknowledge the original work by Michael Maltsev
- Ensure new code is compatible with GPL-3.0 requirements
- Follow the established patterns for attribution and licensing
- Document significant changes in the CHANGES.md file

### Support for Original Project
Users of this enhanced version are encouraged to:
- ⭐ Star the original repository: https://github.com/michael-maltsev/technion-sap-info-fetcher
- Report bugs that might affect both projects to the original repository
- Consider contributing improvements back to the original project when applicable

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

### GPL-3.0 Summary
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

### Commercial Use
Under GPL-3.0, this software can be used commercially, but any modifications or derivative works must also be made available under GPL-3.0. If you use this software in a commercial product, you must provide the source code to your users.