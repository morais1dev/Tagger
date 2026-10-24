# Changelog

All notable changes to Tagger are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Label** ("Gravadora") tag for MP3 (`TPUB`), FLAC/Ogg (`ORGANIZATION`, also reads `LABEL`) and M4A (`LABEL` free-form atom, as Picard writes it). It shows in the editor panel and as an optional column, and works with pending changes.
- **Group by album** (Settings → Behavior, off by default): with more than one album loaded, the list shows a header per album ("Album — Album artist, year", with the track count) and orders the tracks by disc and track. Selection, filter, in-cell editing and the row actions work as before; the header is not a track.

## [2.1.0] — 2026-10-23

### Added
- **FLAC, Ogg Vorbis and M4A/MP4** support, alongside MP3, with the same fields: lyrics, multi-value `A; B`, track/disc totals, and front-cover-only replacement (on M4A, the first image; other embedded images are kept).
- **Look up tags online** (`Ctrl+Shift+M`): search MusicBrainz for the release, match its tracks to your files and fetch the cover from the Cover Art Archive. The results become pending changes, so nothing is written until you save.
- **Organize into folders** (`Ctrl+Shift+O`): move files into folders built from a pattern such as `{albumartist}/{album}/{tracknumber:02} - {title}`, with a live preview. It can be undone, can remove folders left empty, and takes the folder's cover image (`cover`, `folder` or `front`, `.jpg`/`.png`) along, only when the whole folder moves to the same destination.

### Changed
- The ID3 options (ID3v2.3/2.4, removing ID3v1) only apply to MP3. Multi-value applies to every format.
- **Clean up extra tags** also works on FLAC, Ogg and M4A, where it removes the tags Tagger doesn't show (images are always kept). The ID3v1 and unreadable-frame options only apply to MP3.

## [2.0.1] — 2026-10-23

### Fixed
- Pending changes could be lost when you chose **Save** before closing the app, opening another folder, reloading (F5) or cleaning tags, and a file failed to save (read-only, in use…). Tagger now stops and asks whether to go back (changes stay pending) or discard the changes of the files that failed.
- Saving only removals (empty values, removing the cover) on a file without tags no longer creates an empty ID3 header.
- **Clean up extra tags** runs in the background, so the window no longer freezes on large selections.

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
