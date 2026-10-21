# Changelog

All notable changes to Tagger are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-10-21

First release of the desktop app.

### Added
- Graphical interface built with PySide6: folder/file loading, drag & drop, recent folders, search filter, configurable columns and in-cell editing.
- Multi-file editing with ‹various values›, pending changes per file, Save/Discard and undo/redo.
- Cover art: drag, paste, choose, export, save as `cover.jpg` in the folder, and automatic resizing of large images.
- Lyrics field (USLT).
- Rename files from tags with patterns, live preview, conflict detection and undo.
- Fill tags from file names (and parent folders) with patterns.
- Real multi-value tags (`A; B` saved as two values); can be turned off.
- Clean up extra tags: ID3v1, unreadable frames and frames Tagger doesn't show; option to remove ID3v1 on every save.
- Detection of files changed by another program before saving (overwrite / reload / cancel) and **F5** to reload from disk.
- Number tracks, copy/paste tags, themes, accent colors, fonts and density.
- Error log (`tagger.log`) and an error dialog instead of silent crashes.
- Windows executable built with PyInstaller and published by GitHub Actions when a version tag is pushed.
- Automated tests (pytest).

### Changed
- Tags and cover are written in a single save per file.
- Replacing or removing the cover only touches the front cover; other embedded images are kept.
- Files with damaged ID3 tags no longer stop a folder from loading; they are reported as unreadable.
- Dependencies pinned to tested versions (`mutagen 1.48.1`, `PySide6-Essentials 6.12.0`).

## [1.0.0]

- Command-line interface for individual and bulk MP3 tag editing with validation.
