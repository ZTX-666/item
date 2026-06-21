## MODIFIED Requirements

### Requirement: Selection-aware document revision
The system SHALL prefer locked/selected text as the revision target when the user issues an edit command.

#### Scenario: Revise without selection
- **WHEN** the user issues an edit command with no selection and no positional hint (e.g. paragraph index)
- **THEN** the system prompts the user to select text first

#### Scenario: Single definitive revision
- **WHEN** the user requests a document revision with a valid selection
- **THEN** the system returns exactly one final revision text suitable for direct acceptance

## ADDED Requirements

### Requirement: Definitive single revision output
The system SHALL return exactly one revision option for revise, polish, and oral-to-formal tasks.

#### Scenario: Revision API response
- **WHEN** a revise-class task completes successfully
- **THEN** the result contains exactly one option in the options array

#### Scenario: Old text matches selection
- **WHEN** the user had locked/selected text during the revision request
- **THEN** the returned old_text equals the selected text used for the request
