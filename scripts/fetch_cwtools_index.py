#!/usr/bin/env python3
"""
CWTools Index Fetcher - Level 1 Progressive Disclosure

最新のcwtools-stellaris-configから軽量なインデックスを取得する。
名前のリストのみを返し、トークン効率を最大化。

このスクリプトは以下の質問に素早く答える:
- "has_technologyは有効なトリガーか？"
- "create_で始まるエフェクトは何があるか？"
- "どんなスコープがあるか？"

Usage:
    python fetch_cwtools_index.py                    # 全カテゴリのインデックス
    python fetch_cwtools_index.py --category trigger # 特定カテゴリのみ
    python fetch_cwtools_index.py --check has_technology  # 存在確認

Output: JSON形式のインデックス（コンパクト）
"""

import json
import sys
import re
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from github_fetcher import CWToolsFetcher
from cwt_parser import extract_trigger_names, extract_effect_names


# Categories and their source files
CATEGORY_FILES = {
    "trigger": "config/triggers.cwt",
    "effect": "config/effects.cwt",
    "scope": "config/scopes.cwt",
    "enum": "config/enums.cwt",
}


def fetch_index(
    version: str = "master",
    categories: list[str] | None = None,
) -> dict:
    """
    Fetch lightweight index of cwtools elements.

    Args:
        version: "stable" (latest tag), "master", or specific tag
        categories: List of categories to fetch, or None for all

    Returns:
        Dictionary with category -> list of names
    """
    fetcher = CWToolsFetcher(version=version)
    categories = categories or list(CATEGORY_FILES.keys())

    result = {
        "version": fetcher._resolve_version(),
        "categories": {},
    }

    for category in categories:
        if category not in CATEGORY_FILES:
            continue

        try:
            file_path = CATEGORY_FILES[category]
            fetch_result = fetcher.get_file(file_path)
            content = fetch_result.content

            names = []
            if category == "trigger":
                names = extract_trigger_names(content)
            elif category == "effect":
                names = extract_effect_names(content)
            elif category == "scope":
                names = _extract_scope_names(content)
            elif category == "enum":
                names = _extract_enum_names(content)

            result["categories"][category] = {
                "count": len(names),
                "names": names,
                "cached": fetch_result.from_cache,
            }

        except Exception as e:
            result["categories"][category] = {
                "error": str(e),
            }

    return result


def _extract_scope_names(content: str) -> list[str]:
    """Extract scope names from scopes.cwt."""
    names = set()

    # Match both quoted and unquoted scope names
    for match in re.finditer(
        r'(?:"([^"]+)"|(\w+(?:\s+\w+)*))\s*=\s*\{\s*aliases',
        content
    ):
        name = match.group(1) or match.group(2)
        if name:
            names.add(name)

    return sorted(names)


def _extract_enum_names(content: str) -> list[str]:
    """Extract enum names from enums.cwt."""
    names = set()
    for match in re.finditer(r'enum\[(\w+)\]', content):
        names.add(match.group(1))
    return sorted(names)


def check_exists(name: str, version: str = "master") -> dict:
    """
    Check if an element exists and in which category.

    Args:
        name: Element name to check
        version: Version to check against

    Returns:
        Dictionary with existence info and category
    """
    index = fetch_index(version=version)

    result = {
        "name": name,
        "version": index["version"],
        "exists": False,
        "categories": [],
        "partial_matches": [],
    }

    name_lower = name.lower()

    for category, data in index["categories"].items():
        if "error" in data:
            continue

        for element_name in data["names"]:
            element_lower = element_name.lower()
            if element_lower == name_lower:
                result["exists"] = True
                result["categories"].append(category)
            elif name_lower in element_lower:
                result["partial_matches"].append({
                    "name": element_name,
                    "category": category,
                })

    # Limit partial matches
    result["partial_matches"] = result["partial_matches"][:10]

    return result


def filter_names(category: str, pattern: str, version: str = "master") -> dict:
    """
    Filter names by pattern (prefix, suffix, or contains).

    Args:
        category: Category to search in
        pattern: Search pattern (e.g., "create_*", "*_modifier", "*fleet*")
        version: Version to check against

    Returns:
        Dictionary with matching names
    """
    index = fetch_index(version=version, categories=[category])

    if category not in index["categories"]:
        return {"error": f"Unknown category: {category}"}

    data = index["categories"][category]
    if "error" in data:
        return {"error": data["error"]}

    names = data["names"]

    # Convert pattern to regex
    if pattern.startswith("*") and pattern.endswith("*"):
        # Contains
        regex = re.compile(re.escape(pattern[1:-1]), re.IGNORECASE)
        matches = [n for n in names if regex.search(n)]
    elif pattern.startswith("*"):
        # Suffix
        suffix = pattern[1:].lower()
        matches = [n for n in names if n.lower().endswith(suffix)]
    elif pattern.endswith("*"):
        # Prefix
        prefix = pattern[:-1].lower()
        matches = [n for n in names if n.lower().startswith(prefix)]
    else:
        # Exact (case insensitive)
        pattern_lower = pattern.lower()
        matches = [n for n in names if n.lower() == pattern_lower]

    return {
        "version": index["version"],
        "category": category,
        "pattern": pattern,
        "count": len(matches),
        "matches": matches,
    }


def get_summary(version: str = "master") -> dict:
    """
    Get a summary of all categories (counts only, minimal tokens).

    Returns:
        Dictionary with category counts
    """
    index = fetch_index(version=version)

    summary = {
        "version": index["version"],
        "categories": {},
    }

    for category, data in index["categories"].items():
        if "error" in data:
            summary["categories"][category] = {"error": data["error"]}
        else:
            summary["categories"][category] = {"count": data["count"]}

    return summary


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch cwtools index (Level 1 - names only)"
    )
    parser.add_argument(
        "--version",
        default="master",
        help="Version: master (default), or specific commit/tag"
    )
    parser.add_argument(
        "--category",
        choices=["trigger", "effect", "scope", "enum"],
        help="Fetch specific category only"
    )
    parser.add_argument(
        "--check",
        metavar="NAME",
        help="Check if element exists"
    )
    parser.add_argument(
        "--filter",
        metavar="PATTERN",
        help="Filter by pattern (e.g., 'create_*', '*_modifier')"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show counts only (minimal output)"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (no indentation)"
    )

    args = parser.parse_args()

    # Execute based on options
    if args.summary:
        result = get_summary(version=args.version)
    elif args.check:
        result = check_exists(args.check, version=args.version)
    elif args.filter:
        if not args.category:
            print("Error: --filter requires --category", file=sys.stderr)
            sys.exit(1)
        result = filter_names(args.category, args.filter, version=args.version)
    else:
        categories = [args.category] if args.category else None
        result = fetch_index(version=args.version, categories=categories)

    # Output
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
