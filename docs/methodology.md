# Extraction and comparison policy

The adapter is scoped to ORD dataset 805ad863feef48579d95d86a728035f4. It reads actual Protobuf messages through ord-schema's Parquet DatasetView. This is a C–N coupling screen, not a general reaction database.

## Strict identity

Only explicit REACTANT components enter the substrate set. Exactly two core reactants and one unique desired product must have valid SMILES. RDKit canonical isomeric SMILES retain salts, charge, isotopes and stereochemistry; no tautomer or salt stripping. All original identifiers are retained. Order-independent SHA-256 keys group exact substrate sets and desired products. Unclassified inputs exclude a record from strict matching.

## Dataset roles

The source marks both ligands and metal catalysts CATALYST. We distinguish them using the inspected input-map names `ligand soln` / `catalyst soln` AND custom identifier details `Lig_ChemTypeIdx` / `Cat_ChemTypeIdx`. Bases require `base` and `Base_ChemTypeIdx`. SOLVENT components are extracted from every input, preserving the complete composition and recorded amounts. No role depends on ingredient order. A name of `none` is explicit absence only with an `_empty` code; missing identity remains unknown.

## Measurements

Only desired-product YIELD measurements with an explicitly populated percentage value qualify. AREA and side-product yields never substitute. Percentage 50 means 50%. Zero is retained. All qualifying measurements and their analysis references are preserved. Primary selection uses latest known reaction time, authentic-standard calibration, then source indices. Multiple measurements are flagged and never split into separate experiments. Values outside 0–100 remain visible in provenance/diagnostics but do not enter charts or statistics. Summaries use valid primary desired-product yields and sample standard deviation (n−1).

## Comparisons

Tracked factors: substrate quantities, catalyst, ligand, base, full solvent inventory, temperature, reaction duration, pressure/atmosphere, stirring, and other recorded input inventory. Component comparisons include recorded quantities, so an identity match alone does not imply the factor matches. Quantities in component inventories retain original units, conservatively treating different representations as different; temperature normalizes to Celsius and reaction time to hours. Duration comes from reaction outcomes, never filtration or workup time. No other inputs recorded is an inventory state, not proof none were present. Original setup remains inspectable but is not a tracked comparison factor.

Unknown never matches unknown. Any missing tracked factor makes comparison incomplete. Otherwise zero, one or multiple differences determine the classification. Yield methods must match for a percentage-point contrast; incompatible methods produce an incomplete comparison. Candidate search builds signatures omitting one factor, then compares the extremes in each bucket; this is linear in records × tracked fields, not an all-pairs scan. Same-condition signatures identify observations with identical tracked values, not independent laboratory replicates.

These are reported calibrated analytical assay yields, not predictions or necessarily isolated preparative yields. Calibration, unrecorded variables, experimental setup, batches, and measurement variation can affect results. Observational contrasts do not establish causation; yield spread alone is not a reproducibility estimate. Even a single recorded-factor difference is not proof of a controlled experiment.

## Attribution and licenses

Source: Open Reaction Database, dataset `ord_dataset-805ad863feef48579d95d86a728035f4`; _A 50,688-Reaction Data Set Reveals General Ligands and Mechanistic Diversity in C–N Couplings_, https://doi.org/10.1021/jacs.6c05959. Source and derived dataset/report/export content are CC-BY-SA-4.0 (https://creativecommons.org/licenses/by-sa/4.0/). Software is MIT. Code licensing does not relicense the data. Exports carry attribution and the data license. The source is cached locally and the application requires no network after setup/import.

## Observed source coverage

The downloaded SHA-256 is `bef283c5a5cd746d62b86fe97c0924686d9fc3580d05453015fe935bc3c2a531`.
It contains 50,688 distinct ORD IDs and four strict groups, rather than all eight
possible amine/aryl-halide combinations. The actual groups contain 3,072,
6,144, 13,824 and 27,648 records. Two amine identities and four aryl-halide
identities are present. Source outcomes contain 152,064 AREA measurements and
101,376 YIELD measurements across desired products, side products and the
internal standard. Exactly 50,688 desired-product percentage YIELD measurements
are selected. All use LCMS analyses. Twenty reported yields exceed 100%; 50,668
valid yields remain, including 36,433 measured zeros. No value is clipped.

All reactions report 18-hour outcome reaction times; temperatures are 30, 60 or
80 °C. Every tracked field is available in this snapshot. The audit finds 3,676
repeated normalized condition/desired-measurement signatures, with distinct ORD
IDs. These are not established independent replicates or duplicated source
records. The full source messages cannot be byte-identical because their IDs
are distinct. No arbitrary identifier deep links are constructed.

A component with missing quantity or structural ambiguity makes that factor
unavailable. Conflicting same-time desired-product yields remain in provenance
but are excluded from primary-yield summaries, and make measurement comparison
incomplete. The current source has no such conflicts.
