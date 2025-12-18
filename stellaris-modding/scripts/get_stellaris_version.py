#!/usr/bin/env python3
"""
Stellaris Version Information Fetcher

SteamCMD APIを使用してステラリスの現在のバージョン情報を取得する。
MCP Server (kongyo2/Stellaris-Modding-MCP-Server) の実装に基づく。

Usage:
    python get_stellaris_version.py [--json] [--minimal]

Options:
    --json     JSON形式で出力
    --minimal  最小限の情報のみ出力（バージョン番号とビルドIDのみ）

Examples:
    python get_stellaris_version.py
    python get_stellaris_version.py --json
    python get_stellaris_version.py --minimal
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, TypedDict


# Constants
STELLARIS_APP_ID = "281990"
STEAMCMD_API_BASE = "https://api.steamcmd.net/v1"

# Retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,  # seconds
    "max_delay": 10.0,  # seconds
    "backoff_multiplier": 2,
}


class BranchInfo(TypedDict, total=False):
    buildid: str
    timeupdated: str
    description: str


class StellarisVersionResult(TypedDict):
    game_name: str
    current_public: dict[str, Any]
    latest_version: dict[str, Any] | None
    available_versions: list[str]
    special_branches: list[str]
    game_info: dict[str, Any]


def fetch_with_retry(url: str, max_retries: int | None = None) -> dict[str, Any]:
    """
    指数バックオフを使用したリトライ機能付きfetch。

    Args:
        url: 取得するURL
        max_retries: 最大リトライ回数（Noneの場合はRETRY_CONFIG使用）

    Returns:
        パースされたJSONレスポンス

    Raises:
        Exception: リトライ後も失敗した場合
    """
    if max_retries is None:
        max_retries = RETRY_CONFIG["max_retries"]

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Stellaris-Modding-Skill/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data

        except urllib.error.HTTPError as e:
            last_error = e
            # Rate limit or server error - retry
            if e.code in (403, 429, 500, 502, 503, 504):
                if attempt < max_retries:
                    delay = min(
                        RETRY_CONFIG["base_delay"] * (RETRY_CONFIG["backoff_multiplier"] ** attempt),
                        RETRY_CONFIG["max_delay"]
                    )
                    print(f"HTTP {e.code} error, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...",
                          file=sys.stderr)
                    time.sleep(delay)
                    continue
            raise

        except urllib.error.URLError as e:
            last_error = e
            if attempt < max_retries:
                delay = min(
                    RETRY_CONFIG["base_delay"] * (RETRY_CONFIG["backoff_multiplier"] ** attempt),
                    RETRY_CONFIG["max_delay"]
                )
                print(f"Network error, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue
            raise

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = min(
                    RETRY_CONFIG["base_delay"] * (RETRY_CONFIG["backoff_multiplier"] ** attempt),
                    RETRY_CONFIG["max_delay"]
                )
                print(f"Error occurred, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...",
                      file=sys.stderr)
                time.sleep(delay)
                continue
            raise

    raise last_error or Exception("Unknown error during fetch")


def fetch_steam_app_info(app_id: str) -> dict[str, Any]:
    """
    SteamCMD APIからアプリ情報を取得する。

    Args:
        app_id: SteamアプリID

    Returns:
        アプリ情報の辞書

    Raises:
        Exception: API呼び出しが失敗した場合
    """
    url = f"{STEAMCMD_API_BASE}/info/{app_id}"
    data = fetch_with_retry(url)

    if data.get("status") != "success":
        raise Exception(f"API returned error: {json.dumps(data.get('data', {}))}")

    return data.get("data", {}).get(app_id, {})


def format_timestamp(timestamp: str | int) -> str:
    """
    Unix timestampを読みやすい日付形式に変換。

    Args:
        timestamp: Unix timestamp（文字列または整数）

    Returns:
        フォーマットされた日時文字列（JST）
    """
    try:
        ts = int(timestamp)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return "Unknown"


def parse_version_string(version_str: str) -> list[int]:
    """
    バージョン文字列をソート可能な数値リストに変換。

    Args:
        version_str: バージョン文字列（例: "3.14.1"）

    Returns:
        数値のリスト（例: [3, 14, 1]）
    """
    parts = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return parts


def get_stellaris_version() -> StellarisVersionResult:
    """
    ステラリスの現在のバージョン情報を取得する。

    Returns:
        バージョン情報を含む辞書

    Raises:
        Exception: 情報取得に失敗した場合
    """
    app_info = fetch_steam_app_info(STELLARIS_APP_ID)

    branches: dict[str, BranchInfo] = app_info.get("depots", {}).get("branches", {})

    if not branches:
        raise Exception("Branch information not found in API response")

    # Public branch info
    public_branch = branches.get("public", {})

    # Extract version branches (format: X.Y or X.Y.Z)
    version_pattern_branches = []
    for branch_name in branches.keys():
        # Check if branch name looks like a version number
        parts = branch_name.split(".")
        if len(parts) >= 2:
            try:
                # Verify first two parts are numeric
                int(parts[0])
                int(parts[1])
                version_pattern_branches.append(branch_name)
            except ValueError:
                continue

    # Sort by version number (descending)
    version_pattern_branches.sort(
        key=lambda v: parse_version_string(v),
        reverse=True
    )

    # Get latest version info
    latest_version_branch = version_pattern_branches[0] if version_pattern_branches else None
    latest_version_info = branches.get(latest_version_branch, {}) if latest_version_branch else None

    # Build result
    result: StellarisVersionResult = {
        "game_name": app_info.get("common", {}).get("name", "Stellaris"),
        "current_public": {
            "build_id": public_branch.get("buildid"),
            "last_updated": format_timestamp(public_branch.get("timeupdated", "")),
            "last_updated_unix": public_branch.get("timeupdated"),
        },
        "latest_version": None,
        "available_versions": version_pattern_branches[:10],
        "special_branches": [
            b for b in branches.keys()
            if b not in version_pattern_branches and b != "public"
        ],
        "game_info": {
            "app_id": STELLARIS_APP_ID,
            "install_dir": app_info.get("config", {}).get("installdir"),
            "supported_os": app_info.get("common", {}).get("oslist"),
            "developer": app_info.get("extended", {}).get("developer"),
            "publisher": app_info.get("extended", {}).get("publisher"),
        },
    }

    if latest_version_branch and latest_version_info:
        result["latest_version"] = {
            "version": latest_version_branch,
            "build_id": latest_version_info.get("buildid"),
            "description": latest_version_info.get("description", ""),
            "last_updated": format_timestamp(latest_version_info.get("timeupdated", "")),
            "last_updated_unix": latest_version_info.get("timeupdated"),
        }

    return result


def format_human_readable(result: StellarisVersionResult) -> str:
    """
    結果を人間が読みやすい形式にフォーマット。

    Args:
        result: バージョン情報

    Returns:
        フォーマットされた文字列
    """
    lines = [
        "# Stellaris Version Information",
        "",
        "## Current Public Branch",
        f"- Build ID: {result['current_public']['build_id']}",
        f"- Last Updated: {result['current_public']['last_updated']}",
        "",
    ]

    if result["latest_version"]:
        lines.extend([
            "## Latest Version",
            f"- Version: {result['latest_version']['version']}",
            f"- Build ID: {result['latest_version']['build_id']}",
            f"- Description: {result['latest_version']['description'] or 'N/A'}",
            f"- Last Updated: {result['latest_version']['last_updated']}",
            "",
        ])

    lines.extend([
        "## Game Info",
        f"- Game Name: {result['game_name']}",
        f"- App ID: {result['game_info']['app_id']}",
        f"- Install Directory: {result['game_info']['install_dir']}",
        f"- Supported OS: {result['game_info']['supported_os']}",
        f"- Developer: {result['game_info']['developer']}",
        f"- Publisher: {result['game_info']['publisher']}",
        "",
        "## Available Versions (Latest 10)",
    ])

    for version in result["available_versions"]:
        lines.append(f"- {version}")

    if result["special_branches"]:
        lines.extend([
            "",
            "## Special Branches",
        ])
        for branch in result["special_branches"]:
            lines.append(f"- {branch}")

    lines.extend([
        "",
        "---",
        "Data source: SteamCMD API (https://api.steamcmd.net/)",
    ])

    return "\n".join(lines)


def format_minimal(result: StellarisVersionResult) -> str:
    """
    最小限の情報を出力。

    Args:
        result: バージョン情報

    Returns:
        最小限のフォーマット文字列
    """
    version = result["latest_version"]["version"] if result["latest_version"] else "Unknown"
    build_id = result["current_public"]["build_id"] or "Unknown"
    return f"Stellaris {version} (Build {build_id})"


def main() -> int:
    """
    メイン関数。

    Returns:
        終了コード（0: 成功, 1: エラー）
    """
    # Parse arguments
    args = sys.argv[1:]
    output_json = "--json" in args
    output_minimal = "--minimal" in args

    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    try:
        result = get_stellaris_version()

        if output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif output_minimal:
            print(format_minimal(result))
        else:
            print(format_human_readable(result))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
