---
name: stellaris-modding
description: Stellaris modding support skill providing version information, CWTools config access, documentation search, and element validation. Use when working on Stellaris mod development, checking game version compatibility, searching for triggers/effects/modifiers/scopes, or validating mod elements against the current game version.
---

# Stellaris Modding

Stellaris mod開発を支援するスキル。CWToolsバリデーションルールへの動的アクセス、PDXスクリプト構文の検証、バージョン情報の取得を提供。

## References

PDXスクリプトの基礎を理解する必要がある場合に参照:
- **[1.基礎概念.md](references/1.基礎概念.md)**: Clausewitz構文、データ型、演算子、エンコーディング規約

---

## Tools

All scripts are in `scripts/` and require Python 3.10+. No external dependencies.

### 1. Version Info (`get_stellaris_version.py`)

Get current Stellaris version from SteamCMD API.

```bash
python scripts/get_stellaris_version.py           # Human-readable
python scripts/get_stellaris_version.py --json    # JSON format
python scripts/get_stellaris_version.py --minimal # Just "Stellaris X.Y.Z (Build N)"
```

### 2. Element Index (`fetch_cwtools_index.py`)

**Level 1** - Lightweight index for quick lookups. Use first to check existence.

```bash
# Summary (minimal tokens)
python scripts/fetch_cwtools_index.py --summary
# → {"trigger": {"count": 838}, "effect": {"count": 731}, ...}

# Check if element exists
python scripts/fetch_cwtools_index.py --check has_technology
# → {"exists": true, "categories": ["trigger"]}

# Filter by pattern
python scripts/fetch_cwtools_index.py --category trigger --filter "has_*"
python scripts/fetch_cwtools_index.py --category effect --filter "*_modifier"
python scripts/fetch_cwtools_index.py --category effect --filter "*fleet*"

# Full category index
python scripts/fetch_cwtools_index.py --category trigger
```

### 3. Element Details (`fetch_cwtools_element.py`)

**Level 2/3** - Get specific element information.

```bash
# Level 2: Signature (name + type + description)
python scripts/fetch_cwtools_element.py trigger has_technology
python scripts/fetch_cwtools_element.py effect create_fleet

# Level 3: Full definition (includes block content)
python scripts/fetch_cwtools_element.py effect create_fleet --full

# Pattern search (returns multiple matches)
python scripts/fetch_cwtools_element.py effect "create_*"
python scripts/fetch_cwtools_element.py trigger "*_flag"

# Scope info
python scripts/fetch_cwtools_element.py scope Country
python scripts/fetch_cwtools_element.py scope fleet

# Enum values
python scripts/fetch_cwtools_element.py enum fleet_orders
python scripts/fetch_cwtools_element.py enum relative_power_values
```

### 4. Cross-Category Search (`search_cwtools.py`)

Search across all categories by keyword.

```bash
# Basic search (all categories)
python scripts/search_cwtools.py fleet
python scripts/search_cwtools.py technology --limit 15

# Category-specific
python scripts/search_cwtools.py modifier --category trigger --category effect

# Find related elements
python scripts/search_cwtools.py create_fleet --category effect --related

# Find usage examples
python scripts/search_cwtools.py has_technology --category trigger --usage
```

---

## Progressive Disclosure Strategy

Use the minimum level needed:

| Need | Command | Tokens |
|------|---------|--------|
| "Does X exist?" | `--check X` | ~50 |
| "List all X_*" | `--filter "X_*"` | ~100-500 |
| "What does X do?" | `element.py cat X` | ~200 |
| "Full syntax of X" | `element.py cat X --full` | ~500+ |
| "Anything about Y?" | `search.py Y` | ~300-1000 |

---

## Common Patterns

### Validate before writing mod code

```bash
# Check if triggers/effects exist before using them
python scripts/fetch_cwtools_index.py --check has_technology
python scripts/fetch_cwtools_index.py --check add_modifier
```

### Get correct syntax

```bash
# Get signature first
python scripts/fetch_cwtools_element.py effect add_modifier

# If complex, get full definition
python scripts/fetch_cwtools_element.py effect add_modifier --full
```

### Find related elements

```bash
# Don't know exact name? Search
python scripts/search_cwtools.py population --limit 10

# Find similar elements
python scripts/search_cwtools.py create_army --category effect --related
```

### Check valid enum values

```bash
# What values are valid for X?
python scripts/fetch_cwtools_element.py enum leader_classes
python scripts/fetch_cwtools_element.py enum research_areas
```

---

## Output Format

All tools output JSON by default. Add `--compact` for minified output.

Key fields in responses:
- `found`: boolean - whether element was found
- `version`: string - cwtools-stellaris-config version (usually "master")
- `cached`: boolean - whether result came from cache
- `definitions`: array - element definitions (may have multiple overloads)

---

## Caching

Results are cached in `~/.cache/stellaris-modding-skill/` for 24 hours.

```bash
# View cache status
python scripts/github_fetcher.py cache-info

# Clear cache (force fresh data)
python scripts/github_fetcher.py clear-cache
```
