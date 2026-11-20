# Report format

`build_extraction_report` produces this structure; when you write a report
by hand, follow the same contract.

```markdown
# <title>

- structures: N rows
- assays: N rows
- merged relationships: N rows
- status: {"verified": n, "deferred": n, "failed": n}

## Structures
| id | smiles | page |
|---|---|---|
| … |

## Assays
| compound | endpoint | value | unit | page | assay |
|---|---|---|---|---|---|

## Peptide verdicts
| seq_id | notation | form | mass | convention | delta | verdict |
|---|---|---|---|---|---|---|

## Named gaps
- <page>: <what could not be read, verbatim reason>

## Coverage
verified M / rows N; pages covered P / total T
```

Rules:

- Every number carries its page citation.
- Every gap appears in the named-gap list; the report never silently drops
  an unreadable page or an unknown token.
- Potencies carry units and the assay context line from the source.
