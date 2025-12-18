#!/usr/bin/env python3
"""
CWT Parser - Parse cwtools .cwt config files

.cwtファイルをパースして構造化されたデータに変換する。
Progressive Disclosureのために、異なる詳細レベルでの抽出をサポート。

.cwt format overview:
- alias[type:name] = value  →  Defines an alias (trigger, effect, etc.)
- ### comment             →  Documentation for the following definition
- ## option               →  Metadata (scope, cardinality, severity)
- <type_ref>              →  Reference to another type
- scope_group[name]       →  Scope group reference
- enum[name]              →  Enum reference

Usage:
    from cwt_parser import CWTParser, DetailLevel

    parser = CWTParser()
    result = parser.parse(cwt_content)

    # Get at different detail levels
    names = parser.extract_names(result)           # Level 1
    sigs = parser.extract_signatures(result)       # Level 2
    full = parser.extract_full(result)             # Level 3
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class DetailLevel(Enum):
    """Detail level for extraction."""
    NAMES = auto()       # Just names (Level 1)
    SIGNATURES = auto()  # Names + type/structure outline (Level 2)
    FULL = auto()        # Complete definitions (Level 3)


@dataclass
class CWTAlias:
    """Represents a parsed alias definition."""
    category: str        # trigger, effect, etc.
    name: str            # The alias name
    value_type: str      # Simple type or "block"
    description: str     # From ### comments
    metadata: dict       # From ## comments (scope, cardinality, etc.)
    block_content: str   # Raw block content if value_type == "block"
    line_number: int     # For reference
    raw_definition: str  # Complete raw definition

    def to_dict(self, level: DetailLevel = DetailLevel.FULL) -> dict[str, Any]:
        """Convert to dictionary at specified detail level."""
        if level == DetailLevel.NAMES:
            return {"name": self.name, "category": self.category}

        if level == DetailLevel.SIGNATURES:
            result = {
                "name": self.name,
                "category": self.category,
                "type": self.value_type,
            }
            if self.description:
                result["description"] = self.description[:200]  # Truncate
            if self.metadata.get("scope"):
                result["scope"] = self.metadata["scope"]
            return result

        # FULL level
        return {
            "name": self.name,
            "category": self.category,
            "type": self.value_type,
            "description": self.description,
            "metadata": self.metadata,
            "block_content": self.block_content if self.value_type == "block" else None,
            "line_number": self.line_number,
            "raw": self.raw_definition,
        }


@dataclass
class CWTEnum:
    """Represents a parsed enum definition."""
    name: str
    values: list[str]
    line_number: int

    def to_dict(self, level: DetailLevel = DetailLevel.FULL) -> dict[str, Any]:
        if level == DetailLevel.NAMES:
            return {"name": self.name, "count": len(self.values)}
        if level == DetailLevel.SIGNATURES:
            return {"name": self.name, "values": self.values[:10], "total": len(self.values)}
        return {"name": self.name, "values": self.values, "line_number": self.line_number}


@dataclass
class CWTType:
    """Represents a parsed type definition."""
    name: str
    path: str | None
    properties: dict
    line_number: int
    raw_definition: str

    def to_dict(self, level: DetailLevel = DetailLevel.FULL) -> dict[str, Any]:
        if level == DetailLevel.NAMES:
            return {"name": self.name}
        if level == DetailLevel.SIGNATURES:
            return {"name": self.name, "path": self.path}
        return {
            "name": self.name,
            "path": self.path,
            "properties": self.properties,
            "line_number": self.line_number,
        }


@dataclass
class CWTScope:
    """Represents a scope definition."""
    name: str
    aliases: list[str]

    def to_dict(self, level: DetailLevel = DetailLevel.FULL) -> dict[str, Any]:
        return {"name": self.name, "aliases": self.aliases}


@dataclass
class ParseResult:
    """Complete parse result."""
    aliases: list[CWTAlias] = field(default_factory=list)
    enums: list[CWTEnum] = field(default_factory=list)
    types: list[CWTType] = field(default_factory=list)
    scopes: list[CWTScope] = field(default_factory=list)
    scope_groups: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self, level: DetailLevel = DetailLevel.FULL) -> dict[str, Any]:
        return {
            "aliases": [a.to_dict(level) for a in self.aliases],
            "enums": [e.to_dict(level) for e in self.enums],
            "types": [t.to_dict(level) for t in self.types],
            "scopes": [s.to_dict(level) for s in self.scopes],
            "scope_groups": self.scope_groups,
        }

    def get_aliases_by_category(self, category: str) -> list[CWTAlias]:
        """Get all aliases of a specific category."""
        return [a for a in self.aliases if a.category == category]


class CWTParser:
    """Parser for .cwt config files."""

    # Regex patterns
    ALIAS_PATTERN = re.compile(
        r'^alias\[(\w+):([^\]]+)\]\s*=\s*(.+)$',
        re.MULTILINE
    )
    ALIAS_BLOCK_START = re.compile(
        r'^alias\[(\w+):([^\]]+)\]\s*=\s*\{\s*$',
        re.MULTILINE
    )
    DOC_COMMENT = re.compile(r'^###\s*(.+)$', re.MULTILINE)
    META_COMMENT = re.compile(r'^##\s*(.+)$', re.MULTILINE)
    ENUM_BLOCK = re.compile(
        r'enum\[(\w+)\]\s*=\s*\{([^}]+)\}',
        re.MULTILINE | re.DOTALL
    )
    TYPE_BLOCK = re.compile(
        r'type\[(\w+)\]\s*=\s*\{',
        re.MULTILINE
    )
    SCOPE_PATTERN = re.compile(
        r'^\s*(\w+(?:\s+\w+)*)\s*=\s*\{\s*aliases\s*=\s*\{([^}]+)\}\s*\}',
        re.MULTILINE
    )
    SCOPE_GROUP_PATTERN = re.compile(
        r'^\s*(\w+)\s*=\s*\{([^}]+)\}',
        re.MULTILINE
    )

    def __init__(self):
        pass

    def parse(self, content: str, filename: str = "") -> ParseResult:
        """
        Parse .cwt content into structured data.

        Args:
            content: The .cwt file content
            filename: Optional filename for context

        Returns:
            ParseResult with all parsed elements
        """
        result = ParseResult()

        # Detect file type and parse accordingly
        if "scopes = {" in content:
            result.scopes, result.scope_groups = self._parse_scopes_file(content)
        elif "enums = {" in content or "enum[" in content:
            result.enums = self._parse_enums(content)

        if "types = {" in content:
            result.types = self._parse_types(content)

        if "alias[" in content:
            result.aliases = self._parse_aliases(content)

        return result

    def _parse_aliases(self, content: str) -> list[CWTAlias]:
        """Parse all alias definitions."""
        aliases = []
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and pure comments
            if not line or line.startswith("#") and not line.startswith("##"):
                i += 1
                continue

            # Collect preceding comments
            description = ""
            metadata = {}

            # Look back for comments
            j = i - 1
            comment_lines = []
            while j >= 0:
                prev_line = lines[j].strip()
                if prev_line.startswith("###"):
                    comment_lines.insert(0, prev_line[3:].strip())
                elif prev_line.startswith("##"):
                    self._parse_metadata(prev_line[2:].strip(), metadata)
                elif prev_line == "" or prev_line.startswith("#"):
                    pass
                else:
                    break
                j -= 1

            description = " ".join(comment_lines)

            # Check for alias definition
            if line.startswith("alias["):
                alias = self._parse_single_alias(lines, i, description, metadata)
                if alias:
                    aliases.append(alias)
                    # Skip to end of this alias
                    if alias.value_type == "block":
                        # Find matching brace
                        brace_count = 1
                        i += 1
                        while i < len(lines) and brace_count > 0:
                            for ch in lines[i]:
                                if ch == "{":
                                    brace_count += 1
                                elif ch == "}":
                                    brace_count -= 1
                            i += 1
                        continue

            i += 1

        return aliases

    def _parse_single_alias(
        self,
        lines: list[str],
        start_idx: int,
        description: str,
        metadata: dict
    ) -> CWTAlias | None:
        """Parse a single alias definition."""
        line = lines[start_idx].strip()

        # Match alias pattern
        match = re.match(r'^alias\[(\w+):([^\]]+)\]\s*=\s*(.*)$', line)
        if not match:
            return None

        category = match.group(1)
        name = match.group(2).strip()
        value = match.group(3).strip()

        if value == "{" or value.endswith("{"):
            # Block definition
            block_content = self._extract_block(lines, start_idx)
            raw_def = "\n".join(lines[start_idx:start_idx + block_content.count("\n") + 2])
            return CWTAlias(
                category=category,
                name=name,
                value_type="block",
                description=description,
                metadata=metadata,
                block_content=block_content,
                line_number=start_idx + 1,
                raw_definition=raw_def,
            )
        else:
            # Simple definition
            return CWTAlias(
                category=category,
                name=name,
                value_type=value,
                description=description,
                metadata=metadata,
                block_content="",
                line_number=start_idx + 1,
                raw_definition=line,
            )

    def _extract_block(self, lines: list[str], start_idx: int) -> str:
        """Extract block content between { and matching }."""
        result_lines = []
        brace_count = 0
        started = False

        for i in range(start_idx, len(lines)):
            line = lines[i]
            for ch in line:
                if ch == "{":
                    if not started:
                        started = True
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1

            if started:
                result_lines.append(line)

            if started and brace_count == 0:
                break

        return "\n".join(result_lines)

    def _parse_metadata(self, meta_line: str, metadata: dict) -> None:
        """Parse a ## metadata comment into the metadata dict."""
        meta_line = meta_line.strip()

        # Common patterns
        if meta_line.startswith("scope"):
            match = re.match(r'scope\s*=\s*(\w+)', meta_line)
            if match:
                metadata["scope"] = match.group(1)
            elif "any" in meta_line.lower():
                metadata["scope"] = "any"
        elif meta_line.startswith("cardinality"):
            match = re.match(r'cardinality\s*=\s*(\S+)', meta_line)
            if match:
                metadata["cardinality"] = match.group(1)
        elif meta_line.startswith("severity"):
            match = re.match(r'severity\s*=\s*(\w+)', meta_line)
            if match:
                metadata["severity"] = match.group(1)
        elif meta_line.startswith("push_scope"):
            match = re.match(r'push_scope\s*=\s*(\w+)', meta_line)
            if match:
                metadata["push_scope"] = match.group(1)
        elif meta_line.startswith("replace_scope"):
            metadata["replace_scope"] = meta_line

    def _parse_enums(self, content: str) -> list[CWTEnum]:
        """Parse enum definitions."""
        enums = []

        # Find enums block
        enum_block_match = re.search(r'enums\s*=\s*\{', content)
        if enum_block_match:
            # Extract the enums block
            block_start = enum_block_match.end()
            block = self._extract_block_from_pos(content, block_start - 1)

            # Find individual enums within
            for match in re.finditer(r'enum\[(\w+)\]\s*=\s*\{([^}]+)\}', block):
                name = match.group(1)
                values_str = match.group(2)
                values = [v.strip().strip('"') for v in re.findall(r'[\w_-]+|"[^"]+"', values_str)]
                values = [v for v in values if v and not v.startswith("#")]
                enums.append(CWTEnum(
                    name=name,
                    values=values,
                    line_number=content[:match.start()].count("\n") + 1
                ))

        return enums

    def _extract_block_from_pos(self, content: str, start_pos: int) -> str:
        """Extract block content starting from a position."""
        brace_count = 0
        started = False
        end_pos = start_pos

        for i in range(start_pos, len(content)):
            ch = content[i]
            if ch == "{":
                if not started:
                    started = True
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if started and brace_count == 0:
                    end_pos = i + 1
                    break

        return content[start_pos:end_pos]

    def _parse_types(self, content: str) -> list[CWTType]:
        """Parse type definitions."""
        types = []

        # Find types block
        types_match = re.search(r'types\s*=\s*\{', content)
        if not types_match:
            return types

        types_block = self._extract_block_from_pos(content, types_match.end() - 1)

        # Find individual type definitions
        for match in re.finditer(r'type\[(\w+)\]\s*=\s*\{', types_block):
            name = match.group(1)
            type_block = self._extract_block_from_pos(types_block, match.end() - 1)

            # Extract path
            path_match = re.search(r'path\s*=\s*"([^"]+)"', type_block)
            path = path_match.group(1) if path_match else None

            types.append(CWTType(
                name=name,
                path=path,
                properties={},  # Could parse more properties if needed
                line_number=content[:content.find(match.group(0))].count("\n") + 1,
                raw_definition=type_block,
            ))

        return types

    def _parse_scopes_file(self, content: str) -> tuple[list[CWTScope], dict[str, list[str]]]:
        """Parse scopes.cwt file."""
        scopes = []
        scope_groups = {}

        # Find scopes block
        scopes_match = re.search(r'scopes\s*=\s*\{', content)
        if scopes_match:
            scopes_block = self._extract_block_from_pos(content, scopes_match.end() - 1)

            # Parse individual scopes
            for match in re.finditer(
                r'(?:"([^"]+)"|(\w+(?:\s+\w+)*))\s*=\s*\{\s*aliases\s*=\s*\{([^}]+)\}',
                scopes_block
            ):
                name = match.group(1) or match.group(2)
                aliases_str = match.group(3)
                aliases = [a.strip() for a in aliases_str.split() if a.strip()]
                scopes.append(CWTScope(name=name, aliases=aliases))

        # Find scope_groups block
        groups_match = re.search(r'scope_groups\s*=\s*\{', content)
        if groups_match:
            groups_block = self._extract_block_from_pos(content, groups_match.end() - 1)

            for match in re.finditer(r'(\w+)\s*=\s*\{([^}]+)\}', groups_block):
                name = match.group(1)
                members = [m.strip() for m in match.group(2).split() if m.strip()]
                scope_groups[name] = members

        return scopes, scope_groups


def extract_trigger_names(content: str) -> list[str]:
    """Quick extraction of just trigger names from triggers.cwt."""
    names = set()
    for match in re.finditer(r'alias\[trigger:([^\]]+)\]', content):
        names.add(match.group(1).strip())
    return sorted(names)


def extract_effect_names(content: str) -> list[str]:
    """Quick extraction of just effect names from effects.cwt."""
    names = set()
    for match in re.finditer(r'alias\[effect:([^\]]+)\]', content):
        names.add(match.group(1).strip())
    return sorted(names)


def main():
    """CLI interface for the parser."""
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: cwt_parser.py <file.cwt> [--level names|signatures|full] [--category trigger|effect]")
        sys.exit(1)

    filepath = sys.argv[1]
    level = DetailLevel.FULL
    category_filter = None

    # Parse options
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--level":
            level_str = args[i + 1].lower()
            if level_str == "names":
                level = DetailLevel.NAMES
            elif level_str == "signatures":
                level = DetailLevel.SIGNATURES
            else:
                level = DetailLevel.FULL
            i += 2
        elif args[i] == "--category":
            category_filter = args[i + 1]
            i += 2
        else:
            i += 1

    # Read and parse
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parser = CWTParser()
    result = parser.parse(content, filepath)

    # Filter by category if specified
    if category_filter:
        result.aliases = [a for a in result.aliases if a.category == category_filter]

    # Output
    output = result.to_dict(level)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
