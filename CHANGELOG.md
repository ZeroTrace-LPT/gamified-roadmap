# Changelog

All notable changes to this project are recorded here.

## [0.6.0] - 2026-11-03

### Added
- Career dashboard profile with workbook-defined role levels, current phase, total XP, level progress, and XP to the next source-defined level.
- Current mission and next three recommendations from the prerequisite-aware quest service.
- Overall SQLite-backed roadmap completion, plus skill, certification, project, lab-tagged objective, learning-hour, and monthly mission summaries.
- Skill overview bars grouped by source Track and reflecting local progress overlays.
- Dashboard shortcuts to roadmap, quests, skill tree, and workbook import, plus direct current-mission progress editing.
- Scrollable dashboard layout for smaller displays and larger roadmaps.

### Changed
- Application version is now 0.6.0.
- Dashboard mission recommendations now use the same workbook-order and prerequisite-readiness rules as the quest board.

### Known limitations
- Skill overview shows source-defined Skill Matrix and Beyond 25 branches only; prerequisite edges remain absent unless the workbook explicitly provides them.
- Learning-hour totals appear only when estimates are recorded in the source workbook.
- Historical trend charts, achievements, and dedicated certification/project/lab pages remain scheduled for later releases.

## [0.5.0] - 2026-11-03

### Added
- Interactive skill tree containing Skill Matrix skills and Beyond 25 specializations grouped by workbook Track values.
- Skill detail panel with source descriptions, target ages or timeframes, source XP, resources, status, progress, and prerequisite information.
- Search and filters for source tracks, progress state, and unlock state.
- Available, locked, and review-needed states based only on explicit source prerequisite data; no dependency edges are inferred.
- Excel importer support for explicit prerequisite/dependency header columns, stored as structured references in SQLite.
- Shared prerequisite resolution used by the quest board and skill tree.
- Skill Tree page in the application sidebar.

### Changed
- Application version is now 0.5.0.

### Known limitations
- The current workbook contains no structured skill prerequisites. Its 39 skill and specialization nodes are grouped by source Track and have no dependency locks until explicit relationships are supplied in a workbook.
- Skill Matrix `Target Age` values are displayed as written and are not converted to calendar years.

## [0.4.0] - 2026-11-03

### Added
- Quest board derived from every normalized workbook objective, with Main, Side, Certification, Lab, Project, and Boss quest views.
- Lab and purple-team tags from explicit source wording; Boss markers use the workbook's Major milestone priority or explicit final/capstone/purple-team exercise titles.
- Recommended next quests ordered by in-progress work, monthly roadmap sequence, and source sheet order.
- Search and filters for quest class, progress state, and prerequisite readiness.
- Prerequisite resolution for structured source references, including ambiguous and missing dependency handling.
- Explicit user review of narrative workbook prerequisite notes, stored separately from the read-only source snapshot.
- Additive SQLite schema v4 table for prerequisite review history.
- Quest detail panel with source notes, XP rewards, prerequisites, status, and progress editing.

### Changed
- Added Quests to the desktop sidebar between Roadmap and Import data.
- Application version is now 0.4.0.

### Fixed
- Quest recommendations exclude completed, locally blocked, dependency-locked, or unreviewed prerequisite-note items.

### Known limitations
- The workbook contains narrative prerequisite notes but no structured prerequisite edges. Notes are shown as written and require explicit user review; the app does not guess dependency links.
- Items without a workbook XP reward remain unrewarded. Boss classification does not invent XP values.
- Quest classification is a presentation layer; the imported roadmap and its source values remain unchanged.

## [0.3.0] - 2026-11-03

### Added
- Workbook-driven XP award and reversal history stored in an additive SQLite v3 table.
- Career XP and levels parsed from the source Dashboard level table, including source titles, XP bands, unlock requirements, and rewards.
- Separate Track XP for completed items with workbook-defined rewards outside monthly missions and projects.
- Dashboard XP cards, level progress, next source reward, recent XP activity, and mission reward display.
- Source reward and awarded XP details in the roadmap list, timeline, and detail panel.
- Automatic XP synchronization when the active workbook is opened, imported, or progress is edited/reset.
- Gamification tests for source-level parsing, level caps, award idempotency, reversal, re-completion, and schema upgrades.

### Changed
- Career XP includes every normalized project record. The workbook formula's Projects range stops at row 12 although six more project records exist through row 18; the source validation warning remains preserved.
- Application version is now 0.3.0.

### Fixed
- XP availability and completed-reward counts now use the same status precedence as the roadmap progress view.
- Awarded item counts exclude items whose XP balance was fully reversed.

### Known limitations
- The workbook defines ten career levels and no post-Level-10 progression; the app caps progression at the last level present in the source.
- Workbook formulas and cached values are preserved but not recalculated by the application.
- Quest selection, the visual skill tree, achievements, and historical analytics remain scheduled for later releases.

## [0.2.0] - 2026-11-03

### Added
- Searchable roadmap list containing normalized missions, skills, certifications, projects, and learning objectives.
- Filters for item type, category, phase, local progress status, workbook status, and target year.
- Timeline tree grouped by month, year, phase, or source sheet order.
- Roadmap detail panel showing the original workbook status and notes alongside local progress.
- Local progress editing for status, percentage, dates, and notes, with reset-to-source support.
- Additive SQLite schema v2 migration for user-owned progress records.
- Dashboard mission completion and current mission now reflect local progress.

### Changed
- Workbook status and source values remain unchanged when local progress is edited.
- Roadmap page now includes all normalized workbook records instead of only monthly missions.

### Fixed
- Windows packaging now isolates PyInstaller's DLL search path so unrelated host tools cannot add conflicting Qt dependencies.

### Known limitations
- XP awards, level recalculation, quests, skill tree, analytics, dedicated trackers, and Excel export remain scheduled for later releases.
- The workbook's non-standard status values are preserved and shown separately from the app's local progress statuses.
- Local progress is keyed to an imported workbook snapshot. A changed workbook creates a new snapshot; progress transfer between snapshots is deferred.

## [0.1.0] - 2026-10-08

### Added
- Modular PySide6 application shell with Dashboard, Roadmap, and Import data navigation.
- Versioned SQLite schema for source workbook records, normalized roadmap items, validation findings, and local settings.
- Excel importer for `.xlsx` and `.xlsm` files that stores populated cell values, formulas, formula caches, coordinates, validation ranges, and chart series references.
- Normalized source-backed records for the core monthly roadmap and supporting skill, certification, project, and learning tracks.
- Import validation for missing key fields, duplicate source keys, malformed `YYYY-MM` values, circular formulas, and known summary range inconsistencies.
- Idempotent behavior when importing the same workbook content again.
- Initial contributor documentation, development roadmap, requirements, and Windows PyInstaller script.
- Built and smoke-launched the Windows PyInstaller onedir application; packaging excludes optional libraries unused by this release.

### Known limitations
- Roadmap and source pages are read-only in this release; progress editing begins in v0.2.0.
- XP is displayed from the workbook's saved summary. The gamification engine is planned for v0.3.0.
- Excel export, backup/restore, skill tree, quests, achievements, analytics, and the dedicated certification/project/lab views are planned for later versions.
- The packaged executable was smoke-launched in the development environment; a fresh-machine installation validation is deferred to the release-candidate stage.
- The Excel importer preserves source formulas and cached values but does not execute formulas.
