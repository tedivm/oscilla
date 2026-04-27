# Manifest System

## MODIFIED Requirements

### Requirement: YAML manifest envelope structure

All content manifests SHALL use a four-field top-level envelope: `apiVersion`, `kind`, `metadata`, and `spec`. The `apiVersion` field SHALL be `oscilla/v1`. The `kind` field SHALL be one of the registered entity kinds. The `metadata` field SHALL contain at minimum a `name` string that is unique within its kind. The `metadata` field MAY also contain `base: str` to declare inheritance from another same-kind manifest, and `abstract: bool` to mark the manifest as template-only. The `spec` field SHALL contain kind-specific configuration.

#### Scenario: Valid manifest is parsed

- **WHEN** the content loader reads a YAML file with a valid envelope and a recognised `kind`
- **THEN** it parses the file into the corresponding Pydantic manifest model without error

#### Scenario: Unknown kind is rejected

- **WHEN** the content loader reads a YAML file with an unrecognised `kind` value
- **THEN** it raises a validation error identifying the file and the invalid kind

#### Scenario: Missing required envelope field

- **WHEN** a manifest file omits `apiVersion`, `kind`, `metadata`, or `metadata.name`
- **THEN** the loader raises a validation error identifying the missing field and file path

#### Scenario: Abstract manifest with incomplete spec is accepted

- **WHEN** a manifest with `metadata.abstract: true` omits required `spec` fields
- **THEN** the loader does not raise a validation error for the abstract manifest itself

#### Scenario: Manifest with base reference is deferred until base is resolved

- **WHEN** a manifest with `metadata.base: goblin-base` omits required `spec` fields that the base provides
- **THEN** the loader defers Pydantic validation until after merging with the base, then validates the merged result

---

### Requirement: Content loading returns warnings in addition to errors

The `parse()` function SHALL return a 3-tuple of `(List[ManifestEnvelope], List[LoadError], List[LoadWarning])`. The `load_from_text()` and `load_from_disk()` functions SHALL return a 2-tuple of `(ContentRegistry, List[LoadWarning])`. Load warnings are non-fatal issues (e.g., unused abstract manifests) that should be surfaced to authors via `oscilla validate`.

#### Scenario: parse() returns warnings for unused abstract manifests

- **WHEN** an abstract manifest is loaded but never referenced as `metadata.base` by any other manifest
- **THEN** `parse()` includes a `LoadWarning` in the warnings list

#### Scenario: load_from_text() threads warnings through to return value

- **WHEN** `load_from_text()` processes manifests with inheritance warnings
- **THEN** the warnings are included in the returned `List[LoadWarning]`

#### Scenario: load_from_disk() threads warnings through to return value

- **WHEN** `load_from_disk()` processes manifests with inheritance warnings
- **THEN** the warnings are included in the returned `List[LoadWarning]`
