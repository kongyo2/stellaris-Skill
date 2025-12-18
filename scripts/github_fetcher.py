#!/usr/bin/env python3
"""
GitHub Fetcher for cwtools-stellaris-config

GitHubからcwtools-stellaris-configリポジトリのファイルを取得する。
キャッシュ機能付きで、レート制限を回避しつつ最新データを取得可能。

Usage:
    from github_fetcher import CWToolsFetcher

    fetcher = CWToolsFetcher()
    content = fetcher.get_file("config/triggers.cwt")
    files = fetcher.list_directory("config/common")
"""

import json
import hashlib
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# Repository configuration
CWTOOLS_REPO = "cwtools/cwtools-stellaris-config"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

# Cache configuration
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "stellaris-modding-skill"
CACHE_TTL_HOURS = 24  # Re-validate cache after this time


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    content: str
    etag: str | None
    sha: str | None
    fetched_at: str

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "etag": self.etag,
            "sha": self.sha,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        return cls(
            content=data["content"],
            etag=data.get("etag"),
            sha=data.get("sha"),
            fetched_at=data["fetched_at"],
        )


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    content: str
    from_cache: bool
    version_ref: str | None = None  # Tag or commit SHA
    file_path: str = ""


class CWToolsFetcher:
    """
    Fetcher for cwtools-stellaris-config with caching and version support.

    Note: This repo uses "master" as the main branch with the latest content.
    Tags exist but are old version numbers, so "master" is recommended.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        version: str = "master",  # "master" (recommended), or specific commit/tag
    ):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.version = version
        self._resolved_ref: str | None = None
        self._tags_cache: list[str] | None = None

    def _get_cache_path(self, file_path: str) -> Path:
        """Generate cache file path for a given file."""
        # Use hash to handle special characters in paths
        path_hash = hashlib.md5(f"{self.version}:{file_path}".encode()).hexdigest()
        return self.cache_dir / f"{path_hash}.json"

    def _load_cache(self, file_path: str) -> CacheEntry | None:
        """Load cached content if available and not expired."""
        cache_path = self._get_cache_path(file_path)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return CacheEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_cache(self, file_path: str, entry: CacheEntry) -> None:
        """Save content to cache."""
        cache_path = self._get_cache_path(file_path)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False)

    def _is_cache_fresh(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still fresh."""
        try:
            fetched_at = datetime.fromisoformat(entry.fetched_at)
            return datetime.now() - fetched_at < timedelta(hours=CACHE_TTL_HOURS)
        except ValueError:
            return False

    def _fetch_with_retry(
        self,
        url: str,
        headers: dict | None = None,
        max_retries: int = 3,
    ) -> tuple[bytes, dict]:
        """Fetch URL with retry logic."""
        headers = headers or {}
        headers.setdefault("User-Agent", "Stellaris-Modding-Skill/1.0")

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    resp_headers = dict(response.headers)
                    content = response.read()
                    return content, resp_headers

            except urllib.error.HTTPError as e:
                if e.code == 304:  # Not Modified
                    return b"", {"status": "304"}
                if e.code == 404:
                    raise FileNotFoundError(f"File not found: {url}")
                if e.code in (403, 429):  # Rate limit
                    wait = min(2 ** attempt * 5, 60)
                    time.sleep(wait)
                    last_error = e
                    continue
                raise

            except urllib.error.URLError as e:
                wait = min(2 ** attempt, 10)
                time.sleep(wait)
                last_error = e
                continue

        raise last_error or Exception("Max retries exceeded")

    def get_latest_tag(self) -> str:
        """Get the latest release tag from the repository."""
        if self._tags_cache:
            return self._tags_cache[0]

        url = f"{GITHUB_API_BASE}/repos/{CWTOOLS_REPO}/tags"
        content, _ = self._fetch_with_retry(url)
        tags = json.loads(content.decode("utf-8"))

        if not tags:
            raise ValueError("No tags found in repository")

        self._tags_cache = [t["name"] for t in tags]
        return self._tags_cache[0]

    def get_available_tags(self) -> list[str]:
        """Get list of available tags."""
        if self._tags_cache:
            return self._tags_cache

        url = f"{GITHUB_API_BASE}/repos/{CWTOOLS_REPO}/tags"
        content, _ = self._fetch_with_retry(url)
        tags = json.loads(content.decode("utf-8"))

        self._tags_cache = [t["name"] for t in tags]
        return self._tags_cache

    def _resolve_version(self) -> str:
        """Resolve version string to actual ref."""
        if self._resolved_ref:
            return self._resolved_ref

        if self.version == "stable":
            self._resolved_ref = self.get_latest_tag()
        else:
            self._resolved_ref = self.version

        return self._resolved_ref

    def get_file(self, file_path: str, force_refresh: bool = False) -> FetchResult:
        """
        Get file content, using cache when appropriate.

        Args:
            file_path: Path within the repository (e.g., "config/triggers.cwt")
            force_refresh: Force fetch from GitHub even if cached

        Returns:
            FetchResult with content and metadata
        """
        ref = self._resolve_version()

        # Check cache first
        if not force_refresh:
            cached = self._load_cache(file_path)
            if cached and self._is_cache_fresh(cached):
                return FetchResult(
                    content=cached.content,
                    from_cache=True,
                    version_ref=ref,
                    file_path=file_path,
                )

        # Fetch from GitHub raw content
        url = f"{GITHUB_RAW_BASE}/{CWTOOLS_REPO}/{ref}/{file_path}"

        headers = {}
        cached = self._load_cache(file_path)
        if cached and cached.etag:
            headers["If-None-Match"] = cached.etag

        try:
            content_bytes, resp_headers = self._fetch_with_retry(url, headers)

            if resp_headers.get("status") == "304" and cached:
                # Not modified, update cache timestamp
                cached.fetched_at = datetime.now().isoformat()
                self._save_cache(file_path, cached)
                return FetchResult(
                    content=cached.content,
                    from_cache=True,
                    version_ref=ref,
                    file_path=file_path,
                )

            content = content_bytes.decode("utf-8")

            # Save to cache
            entry = CacheEntry(
                content=content,
                etag=resp_headers.get("ETag"),
                sha=None,
                fetched_at=datetime.now().isoformat(),
            )
            self._save_cache(file_path, entry)

            return FetchResult(
                content=content,
                from_cache=False,
                version_ref=ref,
                file_path=file_path,
            )

        except FileNotFoundError:
            raise
        except Exception as e:
            # Fall back to cache if available
            if cached:
                return FetchResult(
                    content=cached.content,
                    from_cache=True,
                    version_ref=ref,
                    file_path=file_path,
                )
            raise

    def list_directory(self, dir_path: str) -> list[dict[str, Any]]:
        """
        List contents of a directory in the repository.

        Args:
            dir_path: Directory path (e.g., "config/common")

        Returns:
            List of file/directory entries with name, type, size, path
        """
        ref = self._resolve_version()
        url = f"{GITHUB_API_BASE}/repos/{CWTOOLS_REPO}/contents/{dir_path}?ref={ref}"

        content, _ = self._fetch_with_retry(url)
        items = json.loads(content.decode("utf-8"))

        return [
            {
                "name": item["name"],
                "type": item["type"],
                "size": item.get("size", 0),
                "path": item["path"],
            }
            for item in items
        ]

    def get_file_list(self, pattern: str = "*.cwt") -> list[str]:
        """
        Get list of all .cwt files in the config directory.

        Returns:
            List of file paths
        """
        result = []

        # Get root config directory
        try:
            items = self.list_directory("config")
        except Exception:
            return result

        for item in items:
            if item["type"] == "file" and item["name"].endswith(".cwt"):
                result.append(item["path"])
            elif item["type"] == "dir":
                # Recurse into subdirectories
                try:
                    sub_items = self.list_directory(item["path"])
                    for sub_item in sub_items:
                        if sub_item["type"] == "file" and sub_item["name"].endswith(".cwt"):
                            result.append(sub_item["path"])
                except Exception:
                    continue

        return sorted(result)

    def clear_cache(self) -> int:
        """Clear all cached files. Returns number of files removed."""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count

    def get_cache_info(self) -> dict[str, Any]:
        """Get information about the cache."""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "cache_dir": str(self.cache_dir),
            "file_count": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }


def main():
    """CLI interface for the fetcher."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: github_fetcher.py <command> [args]")
        print("\nCommands:")
        print("  get <file_path>     - Get file content")
        print("  list <dir_path>     - List directory contents")
        print("  files               - List all .cwt files")
        print("  tags                - List available tags")
        print("  cache-info          - Show cache information")
        print("  clear-cache         - Clear cached files")
        print("\nOptions:")
        print("  --version <ref>     - Use specific version (master, stable, or tag)")
        sys.exit(1)

    # Parse version option
    version = "master"
    args = sys.argv[1:]
    if "--version" in args:
        idx = args.index("--version")
        version = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    command = args[0]
    fetcher = CWToolsFetcher(version=version)

    if command == "get":
        if len(args) < 2:
            print("Usage: github_fetcher.py get <file_path>")
            sys.exit(1)
        result = fetcher.get_file(args[1])
        print(f"# {result.file_path} (version: {result.version_ref}, cached: {result.from_cache})")
        print(result.content)

    elif command == "list":
        if len(args) < 2:
            print("Usage: github_fetcher.py list <dir_path>")
            sys.exit(1)
        items = fetcher.list_directory(args[1])
        for item in items:
            type_char = "d" if item["type"] == "dir" else "f"
            print(f"[{type_char}] {item['name']} ({item['size']} bytes)")

    elif command == "files":
        files = fetcher.get_file_list()
        print(f"Found {len(files)} .cwt files:")
        for f in files:
            print(f"  {f}")

    elif command == "tags":
        tags = fetcher.get_available_tags()
        print("Available tags:")
        for tag in tags[:10]:
            print(f"  {tag}")
        if len(tags) > 10:
            print(f"  ... and {len(tags) - 10} more")

    elif command == "cache-info":
        info = fetcher.get_cache_info()
        print(f"Cache directory: {info['cache_dir']}")
        print(f"Cached files: {info['file_count']}")
        print(f"Total size: {info['total_size_mb']} MB")

    elif command == "clear-cache":
        count = fetcher.clear_cache()
        print(f"Cleared {count} cached files")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
