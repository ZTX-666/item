## MODIFIED Requirements

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
