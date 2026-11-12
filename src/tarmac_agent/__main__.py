"""Command line: ``python -m tarmac_agent [check] [--url URL]``.

``check`` asks a Tarmac server which run modes it can serve, so you know your
setup works before you point an agent at it.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from ._client import TarmacClient
from ._errors import TarmacToolError
from ._version import __version__


def _check(url: str) -> int:
    client = TarmacClient(url, timeout=15.0, retries=1)
    try:
        health = client.health()
    except TarmacToolError as e:
        print(f"✕ {url}: {e.code}: {e.message}", file=sys.stderr)
        return 1
    modes = health.get("modes") or {}
    available = [name for name, m in modes.items() if (m or {}).get("available")]
    print(f"✓ {url} is up")
    print(f"  modes       {', '.join(available) or 'none'}")
    if "persistent" in health:
        print(f"  persistent  {'yes' if health['persistent'] else 'no (runs live on one instance only)'}")
    return 0 if health.get("ok") else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tarmac_agent", description="Tarmac Python SDK")
    parser.add_argument("--version", action="version", version=f"tarmac-agent {__version__}")
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="check that a Tarmac server is reachable and which modes it serves")
    check.add_argument("--url", default=os.environ.get("TARMAC_URL") or "http://localhost:3000", help="server URL (default: $TARMAC_URL or http://localhost:3000)")
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.url)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
