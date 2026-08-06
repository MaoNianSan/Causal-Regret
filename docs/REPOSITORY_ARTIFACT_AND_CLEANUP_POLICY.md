# Repository Artifact and Cleanup Policy

## Tracked by default

- Source code and canonical Python packages.
- Tests and status reports.
- Requirements and configuration files.
- Calibration manifests and canonical provenance records.
- Promoted paper candidate artifacts and figure source CSVs.
- Manuscript macros and figure table source data.
- Canonical current status reports and protocol documents.
- Run manifests that explicitly describe a published or promoted candidate.

## Not tracked by default

- Raw input datasets and licensed external inputs.
- Full raw simulation arrays, intermediate per-seed outputs, and temporary caches.
- Local virtual environments, editor metadata, and runtime scratch files.
- Duplicate PNG/PDF outputs outside authoritative candidate bundles.
- Old generated reports that are not part of the active status or artifact map.
- Debug exports and development snapshots unless explicitly promoted.

## Deletion rules

- Generated artifacts may be deleted only when they are deterministically rebuildable from tracked source and configuration.
- Promoted paper candidates must not be deleted by ordinary cleanup until replacement artifacts are available.
- Calibration artifacts are preserved by cleanup unless the cleanup is explicitly approved to remove them.
- Unverified legacy Full outputs are retained until a new verified Full is produced and reviewed.

## Cleanup behavior

- Cleanup commands default to dry-run or interactive confirmation.
- `--yes` is required for actual deletion.
- Cleanup must never delete raw inputs.
- Cleanup must never delete current promoted paper candidates by default.
- Cleanup results should report deleted paths and reclaimed bytes.
- Cleanup should generate a manifest of deleted files when practical.
