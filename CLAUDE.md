# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code skill for Stellaris modding. It provides tools to fetch and query CWTools validation rules from GitHub, enabling LLM agents to write valid Stellaris mod code.

## Architecture

```
scripts/
├── github_fetcher.py      # Core: GitHub API client with caching
├── cwt_parser.py          # Core: .cwt format parser
├── get_stellaris_version.py    # SteamCMD API integration
├── fetch_cwtools_index.py      # Level 1: Names only (lightweight)
├── fetch_cwtools_element.py    # Level 2/3: Details and full definitions
└── search_cwtools.py           # Cross-category keyword search
```

**Data Sources:**
- SteamCMD API (`api.steamcmd.net`) - Stellaris version info
- GitHub (`cwtools/cwtools-stellaris-config`) - Validation rules for triggers, effects, scopes, enums

**Progressive Disclosure Pattern:**
- Level 1: Names only (~50 tokens) - Use `--check` or `--summary`
- Level 2: Signatures (~200 tokens) - Default output
- Level 3: Full definitions (~500+ tokens) - Use `--full`

## Commands

```bash
# Test scripts
python scripts/get_stellaris_version.py --minimal
python scripts/fetch_cwtools_index.py --summary
python scripts/fetch_cwtools_index.py --check has_technology
python scripts/fetch_cwtools_element.py effect create_fleet
python scripts/search_cwtools.py fleet --limit 5

# Cache management
python scripts/github_fetcher.py cache-info
python scripts/github_fetcher.py clear-cache
```

## Key Design Decisions

- **No external dependencies**: Uses only Python 3.10+ standard library
- **GitHub master branch**: Uses `master` not tags (cwtools repo tags are outdated)
- **24-hour cache TTL**: Balances freshness with rate limit avoidance
- **JSON output**: All scripts output JSON for easy parsing by LLM agents
