# Multi-Manifest Loading

## Purpose

Defines the rules for loading multiple YAML manifests from a single file and for accepting a single file as a complete content path, enabling authors to group related manifests without friction and enabling the future compiled content archive format.

## Requirements

### Requirement: Multi-document YAML files are supported

A single YAML file MAY contain multiple manifest documents separated by `---` document dividers. Each document SHALL be parsed and validated independently as a complete manifest envelope. A file with a single document (no `---` divider) SHALL continue to behave identically to prior behavior.

#### Scenario: Two valid documents in one file both load

- **WHEN** a YAML file contains two valid manifest documents separated by `---`
- **THEN** both manifests are returned by `parse()` with no errors

#### Scenario: Documents of different kinds in one file both load

- **WHEN** a YAML file contains one `Item` document and one `Enemy` document separated by `---`
- **THEN** both manifests are loaded and registered under their respective kinds

#### Scenario: Single-document file behavior is unchanged

- **WHEN** a YAML file contains exactly one manifest with no `---` divider
- **THEN** the manifest loads with no errors and no behavioral difference from prior behavior

---

### Requirement: Load errors in multi-document files include a document index

When a validation error occurs in a file containing more than one document, the error message SHALL include `[doc N]` (1-based) identifying which document within the file caused the error. Single-document files SHALL NOT include a document index in error messages.

#### Scenario: Error in document 2 cites [doc 2]

- **WHEN** a file with two documents has a validation error in the second document
- **THEN** the error message contains `[doc 2]`

#### Scenario: Error in a single-document file has no doc index

- **WHEN** a file with one document has a validation error
- **THEN** the error message does NOT contain `[doc`

#### Scenario: Empty document between dividers is reported as an error

- **WHEN** a file contains `---` followed immediately by another `---` with no content between them
- **THEN** a load error is reported for the empty document, and valid documents in the same file are still loaded

---

### Requirement: `load()` accepts a single file path

The `load(content_path: Path)` function SHALL accept either a directory path (existing behavior) or a path to a single YAML file. When given a file path, all documents in that file are treated as the complete manifest set for the content package. The downstream pipeline (cross-reference validation, template validation, registry build) is unchanged.

#### Scenario: load() with a file path processes all documents

- **WHEN** `load()` is called with a path to a single multi-document YAML file
- **THEN** all documents in the file are parsed and a ContentRegistry is returned with no errors

#### Scenario: load() with a directory path is unchanged

- **WHEN** `load()` is called with a path to a directory
- **THEN** the directory is recursively scanned for `.yaml` and `.yml` files, as before
