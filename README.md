# DIM Intelligence Engine

A config-driven enrichment engine for converting Destiny Item Manager exports into a searchable markdown knowledge base and generating build intelligence reports.

## Phase 2 capabilities
- Export DIM inventory into markdown split by slot, class, equipped state, and loadout
- Build a knowledge pack index from reference markdown files
- Generate `Owned Meta.md` and `Missing Meta.md`
- Generate `Farm Next.md`
- Generate `Best DPS Candidates.md`
- Generate `Set Bonus Candidates.md`
- Generate `Knowledge Pack Index.md`

## Install
```bash
pip install -e .
```

## Usage
```bash
dim-intel inventory.csv --output-dir out
dim-intel inventory.csv --loadouts loadouts.csv --knowledge-dir knowledge --output-dir out
```

## Example reports
- `Kinetic.md`
- `Energy.md`
- `Power.md`
- `Hunter.md`
- `Titan.md`
- `Warlock.md`
- `Equipped Hunter.md`
- `Equipped Titan.md`
- `Equipped Warlock.md`
- `Owned Meta.md`
- `Missing Meta.md`
- `Farm Next.md`
- `Best DPS Candidates.md`
- `Set Bonus Candidates.md`
- `Knowledge Pack Index.md`
