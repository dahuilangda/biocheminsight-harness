# Page taxonomy

Signals to classify patent/literature pages during perception. Every page
gets exactly one primary type; the type decides which stage consumes it.

## Types

| type | signals | consumed by |
|---|---|---|
| `compound_table` | rotated dense tables; cells carry SMILES, peptide notations (`ac-…-am (SEQ ID NO:n)`), potency columns (`Max-Efficacy (nM)`) | structure stage (OCSR / notation ladder) |
| `assay_table` | upright tables reporting measured values per compound (IC50, EC50, Ki, % inhibition) with units and cell lines | assay stage |
| `assay_prose` | Example sections narrating experiments; names endpoints, cell lines, reagents | assay discovery (names + page selection) |
| `structure_drawing` | line-bond drawings, Markush scaffolds with fragment attachments | structure stage (MolDetv2 + OCSR) |
| `prose` | description text without data tables | skipped (except cited figure/page references) |
| `figure_misc` | box plots, scheme figures, flow charts without compound tables | skipped |

## Ambiguity rules

- A compound table with a potency column is still a `compound_table`; its
  potency values are recorded by the structure stage's metadata, and the
  page is excluded from assay discovery.
- A page mixing prose and an assay table is `assay_table`.
- Unreadable orientation: render upright (90° steps) and re-classify once;
  a page unreadable in both orientations is named as a gap.
