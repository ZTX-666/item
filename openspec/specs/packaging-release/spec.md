# packaging-release Specification

## Purpose
TBD - created by archiving change docmate-requirements-baseline. Update Purpose after archive.
## Requirements
### Requirement: Windows portable build
The system SHALL produce a Windows portable executable via `npm run pack` / electron-builder.

#### Scenario: Pack command output
- **WHEN** the developer runs `npm run pack`
- **THEN** a portable build is generated under `release/`

### Requirement: Publish sync to distribution folder
The system SHALL sync source and built artifacts to the configured publish directory (e.g. `publish8/`) via `npm run release`.

#### Scenario: Release pipeline
- **WHEN** the developer runs `npm run release`
- **THEN** the patch version increments, the exe is built, and publish folder is updated

### Requirement: Functional changes require release
The project SHALL run `npm run release` after functional code changes per workspace rule, without manual version bumps.

#### Scenario: Post-feature release
- **WHEN** a functional code change is completed
- **THEN** `npm run release` is executed to bump patch version and sync publish output

