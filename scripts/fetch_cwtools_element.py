#!/usr/bin/env python3
"""
CWTools Element Fetcher - Level 2/3 Progressive Disclosure

特定の要素の詳細情報を取得する。シグネチャ（Level 2）または
フル定義（Level 3）を返す。

このスクリプトは以下の質問に答える:
- "create_fleetの引数は何か？"
- "has_modifierの使い方は？"
- "どのスコープでnum_fleetsを使えるか？"

Usage:
    python fetch_cwtools_element.py trigger has_modifier
    python fetch_cwtools_element.py effect create_fleet --full
    python fetch_cwtools_element.py trigger has_* --list

Output: JSON形式の要素情報
"""

import json
import sys
import re
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from github_fetcher import CWToolsFetcher
from cwt_parser import CWTParser, DetailLevel


CATEGORY_FILES = {
    "trigger": "config/triggers.cwt",
    "effect": "config/effects.cwt",
    "scope": "config/scopes.cwt",
    "enum": "config/enums.cwt",
}


def fetch_element(
    category: str,
    name: str,
    version: str = "master",
    full: bool = False,
) -> dict[str, Any]:
    """
    Fetch detailed information about a specific element.

    Args:
        category: Element category (trigger, effect, scope, enum)
        name: Element name (exact or pattern with *)
        version: Version to fetch from
        full: If True, return full definition (Level 3)

    Returns:
        Dictionary with element details
    """
    if category not in CATEGORY_FILES:
        return {"error": f"Unknown category: {category}"}

    fetcher = CWToolsFetcher(version=version)

    try:
        file_path = CATEGORY_FILES[category]
        fetch_result = fetcher.get_file(file_path)
        content = fetch_result.content

        # Determine detail level
        level = DetailLevel.FULL if full else DetailLevel.SIGNATURES

        # Check if it's a pattern search
        if "*" in name:
            return _search_by_pattern(content, category, name, level, fetch_result)
        else:
            return _find_exact_element(content, category, name, level, fetch_result)

    except Exception as e:
        return {"error": str(e)}


def _find_exact_element(
    content: str,
    category: str,
    name: str,
    level: DetailLevel,
    fetch_result: Any,
) -> dict:
    """Find a specific element by exact name."""
    parser = CWTParser()
    result = parser.parse(content)

    # Find matching aliases
    name_lower = name.lower()
    matches = []

    for alias in result.aliases:
        if alias.category == category and alias.name.lower() == name_lower:
            matches.append(alias.to_dict(level))

    if not matches:
        # Try partial match for suggestions
        suggestions = [
            a.name for a in result.aliases
            if a.category == category and name_lower in a.name.lower()
        ][:5]

        return {
            "found": False,
            "name": name,
            "category": category,
            "version": fetch_result.version_ref,
            "suggestions": suggestions,
        }

    # Return all overloads (some elements have multiple definitions)
    return {
        "found": True,
        "name": name,
        "category": category,
        "version": fetch_result.version_ref,
        "cached": fetch_result.from_cache,
        "definitions": matches,
        "overload_count": len(matches),
    }


def _search_by_pattern(
    content: str,
    category: str,
    pattern: str,
    level: DetailLevel,
    fetch_result: Any,
) -> dict:
    """Search elements by pattern."""
    parser = CWTParser()
    result = parser.parse(content)

    # Convert pattern to regex
    if pattern.startswith("*") and pattern.endswith("*"):
        regex_str = f".*{re.escape(pattern[1:-1])}.*"
    elif pattern.startswith("*"):
        regex_str = f".*{re.escape(pattern[1:])}$"
    elif pattern.endswith("*"):
        regex_str = f"^{re.escape(pattern[:-1])}.*"
    else:
        regex_str = f"^{re.escape(pattern)}$"

    regex = re.compile(regex_str, re.IGNORECASE)

    # Find matching elements
    matches = {}
    for alias in result.aliases:
        if alias.category == category and regex.match(alias.name):
            if alias.name not in matches:
                matches[alias.name] = []
            matches[alias.name].append(alias.to_dict(level))

    return {
        "pattern": pattern,
        "category": category,
        "version": fetch_result.version_ref,
        "cached": fetch_result.from_cache,
        "match_count": len(matches),
        "elements": matches,
    }


def fetch_scope_info(name: str, version: str = "master") -> dict:
    """
    Fetch detailed scope information.

    Args:
        name: Scope name
        version: Version to fetch from

    Returns:
        Scope details including aliases and usable contexts
    """
    fetcher = CWToolsFetcher(version=version)

    try:
        fetch_result = fetcher.get_file("config/scopes.cwt")
        content = fetch_result.content

        parser = CWTParser()
        result = parser.parse(content)

        # Find matching scope
        name_lower = name.lower()

        for scope in result.scopes:
            if scope.name.lower() == name_lower:
                return {
                    "found": True,
                    "name": scope.name,
                    "aliases": scope.aliases,
                    "version": fetch_result.version_ref,
                }

            # Check aliases too
            for alias in scope.aliases:
                if alias.lower() == name_lower:
                    return {
                        "found": True,
                        "name": scope.name,
                        "aliases": scope.aliases,
                        "matched_via_alias": alias,
                        "version": fetch_result.version_ref,
                    }

        # Find in scope groups
        for group_name, members in result.scope_groups.items():
            if name_lower in [m.lower() for m in members]:
                return {
                    "found": True,
                    "name": name,
                    "scope_group": group_name,
                    "group_members": members,
                    "version": fetch_result.version_ref,
                }

        return {
            "found": False,
            "name": name,
            "version": fetch_result.version_ref,
            "available_scopes": [s.name for s in result.scopes],
        }

    except Exception as e:
        return {"error": str(e)}


def fetch_enum_values(name: str, version: str = "master") -> dict:
    """
    Fetch enum values.

    Args:
        name: Enum name
        version: Version to fetch from

    Returns:
        Enum details with all values
    """
    fetcher = CWToolsFetcher(version=version)

    try:
        fetch_result = fetcher.get_file("config/enums.cwt")
        content = fetch_result.content

        parser = CWTParser()
        result = parser.parse(content)

        name_lower = name.lower()

        for enum in result.enums:
            if enum.name.lower() == name_lower:
                return {
                    "found": True,
                    "name": enum.name,
                    "values": enum.values,
                    "count": len(enum.values),
                    "version": fetch_result.version_ref,
                }

        # Suggestions
        suggestions = [e.name for e in result.enums if name_lower in e.name.lower()][:5]

        return {
            "found": False,
            "name": name,
            "suggestions": suggestions,
            "version": fetch_result.version_ref,
        }

    except Exception as e:
        return {"error": str(e)}


def fetch_multiple_elements(
    category: str,
    names: list[str],
    version: str = "master",
    full: bool = False,
) -> dict:
    """
    Fetch multiple elements in one call (more efficient).

    Args:
        category: Element category
        names: List of element names
        version: Version to fetch from
        full: Full details or signatures only

    Returns:
        Dictionary with results for each element
    """
    if category not in CATEGORY_FILES:
        return {"error": f"Unknown category: {category}"}

    fetcher = CWToolsFetcher(version=version)
    level = DetailLevel.FULL if full else DetailLevel.SIGNATURES

    try:
        file_path = CATEGORY_FILES[category]
        fetch_result = fetcher.get_file(file_path)
        content = fetch_result.content

        parser = CWTParser()
        result = parser.parse(content)

        # Build lookup table
        lookup = {}
        for alias in result.aliases:
            if alias.category == category:
                key = alias.name.lower()
                if key not in lookup:
                    lookup[key] = []
                lookup[key].append(alias.to_dict(level))

        # Find each requested element
        results = {}
        for name in names:
            name_lower = name.lower()
            if name_lower in lookup:
                results[name] = {
                    "found": True,
                    "definitions": lookup[name_lower],
                }
            else:
                results[name] = {"found": False}

        return {
            "category": category,
            "version": fetch_result.version_ref,
            "cached": fetch_result.from_cache,
            "results": results,
            "found_count": sum(1 for r in results.values() if r.get("found")),
            "total_requested": len(names),
        }

    except Exception as e:
        return {"error": str(e)}


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch cwtools element details (Level 2/3)"
    )
    parser.add_argument(
        "category",
        choices=["trigger", "effect", "scope", "enum"],
        help="Element category"
    )
    parser.add_argument(
        "name",
        help="Element name (or pattern with *)"
    )
    parser.add_argument(
        "--version",
        default="master",
        help="Version: stable, master, or specific tag"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Return full definition (Level 3)"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output"
    )

    args = parser.parse_args()

    # Handle special cases
    if args.category == "scope":
        result = fetch_scope_info(args.name, version=args.version)
    elif args.category == "enum":
        result = fetch_enum_values(args.name, version=args.version)
    else:
        result = fetch_element(
            args.category,
            args.name,
            version=args.version,
            full=args.full,
        )

    # Output
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
