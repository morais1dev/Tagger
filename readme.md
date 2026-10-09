# Tagger

Tagger is a command-line utility designed for editing and managing audio file metadata. Currently focused on MP3 files, the application provides a streamlined interface for both individual file editing and bulk tag application.

## Versions
- **v1.0 (Current):** Command-line interface (CLI) featuring a solid backend architecture for individual and bulk MP3 metadata editing.
- **2.0 (Planned):** Desktop application transitioning the current backend to a graphical user interface (GUI) built with Python and Tkinter.
- **v3.0 (Planned):** Full cross-platform application (Web and Mobile) developed with Flutter and Dart, expanding the tool to mobile devices and browsers.

## Current Features

- **Individual Editing:** Select a specific file and edit its tags interactively.
- **Bulk Editing:** Apply the same tag values (e.g., Artist, Album, Genre, Year) to multiple files simultaneously.
- **Data Validation:** Built-in validation rules to ensure metadata integrity (e.g., strict 4-digit year format, valid track numbering).
- **Clean CLI:** Clear terminal interface using standard OS clearing commands for better readability.

## Roadmap / Future Implementations

The current version establishes a solid foundation for metadata manipulation. The following features are planned for future releases:

- **Expanded Format Support:** Compatibility with FLAC, WAV, OGG, and other audio formats.
- **Automated Metadata Fetching:** Integration with Last.fm and Discogs APIs to retrieve tags automatically.
- **File Standardization:** Automated file renaming and directory structuring based on metadata tags.
- **Graphical User Interface (GUI):** Transitioning from the CLI to a full desktop or mobile interface (potentially via Flutter/Dart, PyQt, or CustomTkinter).
- **Advanced Tagging Options:** Support for album art injection, lyrics, and custom metadata fields.

## Technologies Used

- Python 3.x
- Mutagen (for audio metadata manipulation)
- Tkinter (for native OS file selection dialogs)

## Installation and Usage

1. Clone the repository to your local machine.
2. Install the required dependencies:
   ```bash
   pip install mutagen
   ```
3. Run the main script:
   ```bash
   python main.py
   ```