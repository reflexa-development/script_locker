from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .packer import pack_resource


def _positive_dir(path: str) -> str:
    p = Path(path)
    if not p.exists() or not p.is_dir():
        raise argparse.ArgumentTypeError(f"Not a directory: {path}")
    return path


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="fivem-locker",
        description="FiveM resource script locker/obfuscator",
    )
    parser.add_argument("resource_dir", type=_positive_dir, help="Path to the resource directory (with fxmanifest.lua)")
    parser.add_argument("-o", "--out", dest="out", help="Output directory for locked resource (default: <name>-locked)")
    parser.add_argument("--key", dest="key", help="Passphrase to embed; defaults to random if omitted")
    parser.add_argument("--client-only", action="store_true", help="Only include client and shared scripts")
    parser.add_argument("--server-only", action="store_true", help="Only include server and shared scripts")
    parser.add_argument("--version", action="version", version=f"fivem-locker {__version__}")

    args = parser.parse_args(argv)

    resource_dir = Path(args.resource_dir)
    name = resource_dir.name
    out_dir = Path(args.out) if args.out else resource_dir.with_name(f"{name}-locked")

    include_client = not args.server_only
    include_server = not args.client_only

    guidance = pack_resource(
        str(resource_dir),
        str(out_dir),
        key=args.key,
        include_client=include_client,
        include_server=include_server,
    )

    print("\nLocked resource written to:", guidance["resource_out"])
    print("Key (embedded in loaders):", guidance["key"])  # Reminder: obfuscation only


if __name__ == "__main__":
    main()
