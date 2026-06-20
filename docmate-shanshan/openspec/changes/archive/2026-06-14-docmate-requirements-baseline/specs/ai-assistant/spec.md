## ADDED Requirements

### Requirement: Multi-mode AI assistant
The system SHALL support agent modes: revise, polish, QA, risk scan, oral-to-formal, and smart table generation.

#### Scenario: Intent routing from natural language
- **WHEN** the user sends a command in the AI panel without specifying a mode
- **THEN** the system routes to the appropriate mode based on intent classification

### Requirement: Selection-aware document revision
The system SHALL prefer locked/selected text as the revision target when the user issues an edit command.

#### Scenario: Revise without selection
- **WHEN** the user issues an edit command with no selection and no positional hint (e.g. paragraph index)
- **THEN** the system prompts the user to select text first

### Requirement: Streaming QA responses
The system SHALL stream assistant answers in QA mode with visible incremental output.

#### Scenario: QA streaming display
- **WHEN** the user asks a question about the document in QA mode
- **THEN** the answer appears incrementally in the chat panel until complete

### Requirement: Risk scan with locate and actions
The system SHALL list risk items from document scan and allow the user to locate, accept, or ignore each item.

#### Scenario: Risk item locate
- **WHEN** the user clicks locate on a risk item
- **THEN** the editor scrolls to or highlights the referenced text

### Requirement: Revision history
The system SHALL record AI revision history entries viewable in a dedicated panel tab.

#### Scenario: View revision history
- **WHEN** the user opens the history tab in the AI panel
- **THEN** past revision entries are listed with enough context to review

### Requirement: Planned continuous document dialogue
The system SHALL support multi-turn edit conversations that retain context across commands. **[PLANNED — Phase 2]**

#### Scenario: Follow-up edit command
- **WHEN** the user sends a follow-up edit referring to a prior AI change
- **THEN** the system applies the command using prior turn context
