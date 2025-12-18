#!/usr/bin/env python3
"""
CWTools Search - Cross-category keyword search

全カテゴリを横断してキーワード検索を行う。
トリガー、エフェクト、スコープ、列挙型を一度に検索可能。

このスクリプトは以下の質問に答える:
- "fleetに関連する要素は何があるか？"
- "modifierを操作する方法は？"
- "populationに関するトリガーとエフェクトは？"

Usage:
    python search_cwtools.py fleet
    python search_cwtools.py "add_modifier" --category effect
    python search_cwtools.py technology --limit 20

Output: JSON形式の検索結果
"""

import json
import sys
import re
from pathlib import Path
from typing import Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

from github_fetcher import CWToolsFetcher
from cwt_parser import CWTParser, DetailLevel


CATEGORY_FILES = {
    "trigger": "config/triggers.cwt",
    "effect": "config/effects.cwt",
    "scope": "config/scopes.cwt",
    "enum": "config/enums.cwt",
}


@dataclass
class SearchResult:
    """A single search result."""
    category: str
    name: str
    match_type: str  # "name", "description", "value"
    relevance: int   # Higher = more relevant
    snippet: str     # Context snippet


def search_cwtools(
    query: str,
    version: str = "master",
    categories: list[str] | None = None,
    limit: int = 50,
    include_descriptions: bool = True,
) -> dict[str, Any]:
    """
    Search across cwtools config files.

    Args:
        query: Search query (keyword or phrase)
        version: Version to search
        categories: Categories to search (None = all)
        limit: Maximum results per category
        include_descriptions: Also search in descriptions

    Returns:
        Dictionary with search results
    """
    fetcher = CWToolsFetcher(version=version)
    categories = categories or list(CATEGORY_FILES.keys())

    query_lower = query.lower()
    query_pattern = re.compile(re.escape(query), re.IGNORECASE)

    results = {
        "query": query,
        "version": fetcher._resolve_version(),
        "categories": {},
        "total_matches": 0,
    }

    for category in categories:
        if category not in CATEGORY_FILES:
            continue

        try:
            file_path = CATEGORY_FILES[category]
            fetch_result = fetcher.get_file(file_path)
            content = fetch_result.content

            category_results = _search_in_content(
                content,
                category,
                query_lower,
                query_pattern,
                include_descriptions,
                limit,
            )

            results["categories"][category] = {
                "matches": category_results,
                "count": len(category_results),
                "cached": fetch_result.from_cache,
            }
            results["total_matches"] += len(category_results)

        except Exception as e:
            results["categories"][category] = {"error": str(e)}

    return results


def _search_in_content(
    content: str,
    category: str,
    query_lower: str,
    query_pattern: re.Pattern,
    include_descriptions: bool,
    limit: int,
) -> list[dict]:
    """Search within a single file's content."""
    parser = CWTParser()
    parsed = parser.parse(content)

    matches = []

    # Search in aliases
    for alias in parsed.aliases:
        if alias.category != category:
            continue

        relevance = 0
        match_type = None
        snippet = ""

        # Check name match
        if query_lower in alias.name.lower():
            if alias.name.lower() == query_lower:
                relevance = 100  # Exact match
                match_type = "exact_name"
            elif alias.name.lower().startswith(query_lower):
                relevance = 80  # Prefix match
                match_type = "prefix"
            else:
                relevance = 60  # Contains
                match_type = "name_contains"
            snippet = alias.name

        # Check description
        elif include_descriptions and alias.description:
            if query_lower in alias.description.lower():
                relevance = 40
                match_type = "description"
                # Extract snippet around match
                snippet = _extract_snippet(alias.description, query_pattern)

        # Check value/block content
        elif alias.value_type == "block" and query_lower in alias.block_content.lower():
            relevance = 20
            match_type = "definition"
            snippet = _extract_snippet(alias.block_content, query_pattern)

        if relevance > 0:
            matches.append({
                "name": alias.name,
                "type": alias.value_type,
                "match_type": match_type,
                "relevance": relevance,
                "snippet": snippet[:200] if snippet else "",
                "description": alias.description[:150] if alias.description else "",
                "scope": alias.metadata.get("scope"),
            })

    # Search in enums (for enum category)
    if category == "enum":
        for enum in parsed.enums:
            if query_lower in enum.name.lower():
                matches.append({
                    "name": enum.name,
                    "type": "enum",
                    "match_type": "name_contains",
                    "relevance": 60 if enum.name.lower().startswith(query_lower) else 40,
                    "value_count": len(enum.values),
                    "sample_values": enum.values[:5],
                })
            else:
                # Search in enum values
                matching_values = [v for v in enum.values if query_lower in v.lower()]
                if matching_values:
                    matches.append({
                        "name": enum.name,
                        "type": "enum",
                        "match_type": "value_contains",
                        "relevance": 30,
                        "matching_values": matching_values[:5],
                    })

    # Search in scopes
    if category == "scope":
        for scope in parsed.scopes:
            if query_lower in scope.name.lower():
                matches.append({
                    "name": scope.name,
                    "type": "scope",
                    "match_type": "name_contains",
                    "relevance": 70,
                    "aliases": scope.aliases,
                })
            else:
                # Search in aliases
                matching_aliases = [a for a in scope.aliases if query_lower in a.lower()]
                if matching_aliases:
                    matches.append({
                        "name": scope.name,
                        "type": "scope",
                        "match_type": "alias_contains",
                        "relevance": 50,
                        "matching_aliases": matching_aliases,
                    })

        # Search in scope groups
        for group_name, members in parsed.scope_groups.items():
            if query_lower in group_name.lower():
                matches.append({
                    "name": group_name,
                    "type": "scope_group",
                    "match_type": "name_contains",
                    "relevance": 60,
                    "members": members,
                })

    # Sort by relevance and limit
    matches.sort(key=lambda x: x["relevance"], reverse=True)
    return matches[:limit]


def _extract_snippet(text: str, pattern: re.Pattern, context_chars: int = 50) -> str:
    """Extract a snippet around the first match."""
    match = pattern.search(text)
    if not match:
        return text[:100]

    start = max(0, match.start() - context_chars)
    end = min(len(text), match.end() + context_chars)

    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet.replace("\n", " ").replace("\t", " ")


def search_related(
    element_name: str,
    category: str,
    version: str = "master",
) -> dict[str, Any]:
    """
    Find related elements to a given element.

    Searches for elements that:
    - Have similar names
    - Reference the given element
    - Are referenced by the given element

    Args:
        element_name: Base element name
        category: Element category
        version: Version to search

    Returns:
        Related elements grouped by relationship type
    """
    fetcher = CWToolsFetcher(version=version)

    if category not in CATEGORY_FILES:
        return {"error": f"Unknown category: {category}"}

    try:
        file_path = CATEGORY_FILES[category]
        fetch_result = fetcher.get_file(file_path)
        content = fetch_result.content

        parser = CWTParser()
        parsed = parser.parse(content)

        element_lower = element_name.lower()

        # Find the base element
        base_element = None
        for alias in parsed.aliases:
            if alias.category == category and alias.name.lower() == element_lower:
                base_element = alias
                break

        if not base_element:
            return {
                "error": f"Element not found: {element_name}",
                "category": category,
            }

        # Find related elements
        similar_names = []
        references_element = []
        referenced_by = []

        # Extract base name parts for similarity matching
        name_parts = set(re.split(r'[_\s]', element_lower))

        for alias in parsed.aliases:
            if alias.category != category:
                continue
            if alias.name.lower() == element_lower:
                continue

            alias_lower = alias.name.lower()
            alias_parts = set(re.split(r'[_\s]', alias_lower))

            # Check for similar names (shared word parts)
            common_parts = name_parts & alias_parts
            if len(common_parts) >= 1 and any(len(p) > 3 for p in common_parts):
                similar_names.append({
                    "name": alias.name,
                    "common_parts": list(common_parts),
                })

            # Check if this element references the base element
            if base_element.name in alias.block_content or base_element.name in alias.value_type:
                references_element.append(alias.name)

            # Check if base element references this element
            if alias.name in base_element.block_content:
                referenced_by.append(alias.name)

        return {
            "element": element_name,
            "category": category,
            "version": fetch_result.version_ref,
            "similar_names": similar_names[:10],
            "references_this": references_element[:10],
            "referenced_by": referenced_by[:10],
        }

    except Exception as e:
        return {"error": str(e)}


def get_usage_examples(
    element_name: str,
    category: str,
    version: str = "master",
) -> dict[str, Any]:
    """
    Get usage context for an element by finding how it's used in definitions.

    Args:
        element_name: Element to find usage for
        category: Element category
        version: Version to search

    Returns:
        Usage examples and context
    """
    fetcher = CWToolsFetcher(version=version)

    # Search across multiple files
    files_to_search = [
        "config/triggers.cwt",
        "config/effects.cwt",
        "config/common/buildings.cwt",
        "config/common/technologies_consolidated.cwt",
        "config/events.cwt",
    ]

    usages = []

    for file_path in files_to_search:
        try:
            fetch_result = fetcher.get_file(file_path)
            content = fetch_result.content

            # Find lines containing the element
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if element_name in line:
                    # Get context (2 lines before and after)
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context = "\n".join(lines[start:end])

                    usages.append({
                        "file": file_path,
                        "line": i + 1,
                        "context": context,
                    })

                    if len(usages) >= 10:
                        break

        except Exception:
            continue

        if len(usages) >= 10:
            break

    return {
        "element": element_name,
        "category": category,
        "version": fetcher._resolve_version(),
        "usage_count": len(usages),
        "usages": usages,
    }


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Search cwtools config files"
    )
    parser.add_argument(
        "query",
        help="Search query"
    )
    parser.add_argument(
        "--version",
        default="master",
        help="Version: stable, master, or specific tag"
    )
    parser.add_argument(
        "--category",
        choices=["trigger", "effect", "scope", "enum"],
        action="append",
        help="Search specific category (can specify multiple)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results per category"
    )
    parser.add_argument(
        "--related",
        action="store_true",
        help="Find related elements instead of keyword search"
    )
    parser.add_argument(
        "--usage",
        action="store_true",
        help="Find usage examples"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output"
    )

    args = parser.parse_args()

    # Execute based on mode
    if args.related:
        if not args.category:
            print("Error: --related requires --category", file=sys.stderr)
            sys.exit(1)
        result = search_related(args.query, args.category[0], version=args.version)
    elif args.usage:
        if not args.category:
            print("Error: --usage requires --category", file=sys.stderr)
            sys.exit(1)
        result = get_usage_examples(args.query, args.category[0], version=args.version)
    else:
        result = search_cwtools(
            args.query,
            version=args.version,
            categories=args.category,
            limit=args.limit,
        )

    # Output
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
