# Domain Docs

Chapter 13 uses a single-context domain-documentation layout rooted at `chapter13/`.

## Before exploring, read these

- `chapter13/CONTEXT.md`, when it exists
- Relevant ADRs under `chapter13/docs/adr/`, when they exist

If these files do not exist, proceed silently. Do not create them preemptively. `/domain-modeling`, `/grill-with-docs`, or `/improve-codebase-architecture` creates them lazily when terminology or decisions are resolved.

## File structure

```text
chapter13/
├── CONTEXT.md
├── docs/
│   └── adr/
└── code/
```

## Use the glossary's vocabulary

When naming a domain concept in an issue, proposal, hypothesis, or test, use the term defined in `chapter13/CONTEXT.md`. Avoid synonyms that the glossary rejects.

If a needed concept is absent, reconsider whether the term belongs to the project or record the gap for `/domain-modeling`.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding the decision.
