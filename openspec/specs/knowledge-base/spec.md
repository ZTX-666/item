# knowledge-base Specification

## Purpose
TBD - created by archiving change docmate-requirements-baseline. Update Purpose after archive.
## Requirements
### Requirement: User knowledge base document
The system SHALL allow users to maintain a persistent knowledge-base text (style guides, terminology, org rules).

#### Scenario: Edit knowledge base
- **WHEN** the user opens the knowledge base modal and saves content
- **THEN** the content persists across app restarts

### Requirement: Knowledge base injected into prompts
The system SHALL prepend the knowledge base to relevant LLM prompts so AI output follows user-defined rules.

#### Scenario: Revision with knowledge base
- **WHEN** the user triggers an AI revision and the knowledge base is non-empty
- **THEN** the LLM request includes the knowledge base as mandatory context

