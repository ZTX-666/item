## ADDED Requirements

### Requirement: Portable workspace storage
In portable mode, the system SHALL store user documents under `DocMateData` adjacent to the executable.

#### Scenario: Portable data directory
- **WHEN** the user runs the portable exe or bat launcher
- **THEN** workspace files are read and written under the portable `DocMateData` folder

### Requirement: File tree navigation
The system SHALL display a workspace file tree and allow opening, creating, and saving markdown documents.

#### Scenario: Create new document
- **WHEN** the user creates a new file in the workspace
- **THEN** the file appears in the tree and opens in the editor

#### Scenario: Import external file
- **WHEN** the user imports a file from disk
- **THEN** the file is copied or linked into the workspace and opened

### Requirement: Open workspace folder
The system SHALL allow opening the workspace directory in the OS file manager.

#### Scenario: Open folder action
- **WHEN** the user chooses to open the workspace folder
- **THEN** the system shell opens the workspace path
