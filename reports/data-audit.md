# ORD source data audit

Dataset: `ord_dataset-805ad863feef48579d95d86a728035f4`

SHA-256: `bef283c5a5cd746d62b86fe97c0924686d9fc3580d05453015fe935bc3c2a531`

Imported UTC: 2026-11-02T12:23:26.171758+00:00

## Counts

- record_count: 50688
- usable_identifiers: 50688
- strict_identity_records: 50688
- comparable_groups: 4
- usable_yields: 50668
- zero_yields: 36433
- duplicate_ids: 0
- duplicate_normalized_records: 3676

## Field coverage

- substrate_amounts: 50688/50688
- catalyst: 50688/50688
- ligand: 50688/50688
- base: 50688/50688
- solvent: 50688/50688
- temperature: 50688/50688
- duration: 50688/50688
- atmosphere: 50688/50688
- stirring: 50688/50688
- other: 50688/50688

## Diagnostics

- out_of_range_yield: 20

See `data-audit.json` for exact condition values, package versions and group counts. See `docs/methodology.md` for the extraction and comparison policy. Reported values outside 0–100 are retained in measurement provenance but excluded from summaries; no clipping. Duplicate normalized signatures are observations, not proof of independent replicates. Source records are retained once per source row.

Attribution: Open Reaction Database and the authors of https://doi.org/10.1021/jacs.6c05959. Derived data: CC-BY-SA-4.0.
