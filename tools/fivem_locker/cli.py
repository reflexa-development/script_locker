import argparse
import sys
from pathlib import Path

from .core import process_resource


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fivem-locker",
        description="Lock/obfuscate FiveM Lua resources with minify+encryption and license gating",
    )
    parser.add_argument("resource_dir", type=Path, help="Path to FiveM resource directory")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output directory for locked resource")
    parser.add_argument("--license", "-k", type=str, required=True, help="License key to bind encryption")
    parser.add_argument("--salt", type=str, default="fivem-locker", help="Optional salt for key derivation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv or sys.argv[1:])
    try:
        process_resource(
            resource_dir=ns.resource_dir,
            output_dir=ns.output,
            license_key=ns.license,
            salt=ns.salt,
            verbose=ns.verbose,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[fivem-locker] error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
