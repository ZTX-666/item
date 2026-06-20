# editor-core Specification

## Purpose
TBD - created by archiving change docmate-requirements-baseline. Update Purpose after archive.
## Requirements
### Requirement: Minimal writing-board editor
The system SHALL provide a Tiptap-based editor with a clean, distraction-free layout suitable for pasting and editing long-form Chinese documents.

#### Scenario: User pastes document text
- **WHEN** the user pastes text into the editor
- **THEN** the content appears in the main editing area without extra dialog steps

### Requirement: Sticky text selection
The system SHALL keep the user's text selection highlighted until the user clicks the same selected text again or explicitly clears the selection.

#### Scenario: Selection persists when focusing AI panel
- **WHEN** the user selects text in the editor and then clicks the AI panel or input field
- **THEN** the blue selection highlight remains visible

#### Scenario: Selection clears on re-click
- **WHEN** the user clicks the already-selected text again
- **THEN** the selection is cleared

### Requirement: Inline AI bubble menu on selection
The system SHALL show an operation bar above the selected text for AI-driven edits (e.g. revise selection).

#### Scenario: Bubble menu appears after selection
- **WHEN** the user finishes dragging to select text
- **THEN** an inline menu appears near the selection for AI actions

### Requirement: Diff review before replace
The system SHALL show old text (deletion style) and new text (addition style) and require explicit accept or reject before modifying the document.

#### Scenario: User accepts AI revision
- **WHEN** the user clicks accept on a diff preview
- **THEN** the editor content is updated at the locked selection coordinates and the diff UI closes

#### Scenario: User rejects AI revision
- **WHEN** the user clicks reject on a diff preview
- **THEN** the original text remains unchanged

#### Scenario: Accept with sticky selection
- **WHEN** the user accepts a revision that was previewed on a sticky selection
- **THEN** the system replaces the document range at the stored selection coordinates without requiring a second text search

### Requirement: Manual editing coexists with AI
The system SHALL allow direct cursor editing at any time without disabling AI features.

#### Scenario: User edits while selection exists
- **WHEN** the user types in the editor during an active AI session
- **THEN** manual edits apply immediately without blocking the editor

