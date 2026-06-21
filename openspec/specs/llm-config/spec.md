# llm-config Specification

## Purpose
TBD - created by archiving change docmate-requirements-baseline. Update Purpose after archive.
## Requirements
### Requirement: Configurable online LLM
The system SHALL let users configure API URL, API key, and model name from the in-app settings modal.

#### Scenario: Save LLM settings
- **WHEN** the user saves valid LLM settings
- **THEN** subsequent AI calls use the configured endpoint and model

### Requirement: Connection test
The system SHALL provide a test action that verifies connectivity to the configured LLM endpoint.

#### Scenario: Successful connection test
- **WHEN** the user runs connection test with valid credentials
- **THEN** the UI reports success

#### Scenario: Failed connection test
- **WHEN** the user runs connection test with invalid credentials or network failure
- **THEN** the UI reports a clear error without exposing the full API key

### Requirement: API key protection
The system SHALL keep LLM API keys in the Electron main process and never expose them to renderer devtools by default.

#### Scenario: Settings retrieval for UI
- **WHEN** the settings UI loads
- **THEN** the displayed key is masked or omitted while still allowing updates

### Requirement: Offline simulation mode
The system SHALL fall back to simulated AI responses when online API is disabled or unavailable for development/demo.

#### Scenario: API disabled
- **WHEN** `useApi` is false or no API key is set
- **THEN** AI features return simulated results instead of failing silently

