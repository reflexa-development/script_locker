from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .lua_minify import minify_lua
from .crypto import LockerCrypto
from .manifest import read_manifest, write_manifest, ManifestData
from .loader import generate_loader


@dataclass
class FileEntry:
    path: Path
    rel_path: Path
    is_lua: bool


def iter_files(root: Path) -> Iterable[FileEntry]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        is_lua = p.suffix.lower() == ".lua"
        yield FileEntry(path=p, rel_path=rel, is_lua=is_lua)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def process_resource(resource_dir: Path, output_dir: Path, license_key: str, salt: str, verbose: bool = False) -> None:
    resource_dir = resource_dir.resolve()
    output_dir = output_dir.resolve()

    if not resource_dir.exists():
        raise FileNotFoundError(f"resource_dir not found: {resource_dir}")

    # Clean output
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)

    manifest = read_manifest(resource_dir)

    crypto = LockerCrypto(license_key=license_key, salt=salt)

    # Separate bundles for client and server; shared goes to both
    bundled_client: dict[str, bytes] = {}
    bundled_server: dict[str, bytes] = {}

    # Copy non-Lua files directly; process Lua files
    for entry in iter_files(resource_dir):
        out_path = output_dir / entry.rel_path
        ensure_dir(out_path.parent)
        if entry.rel_path.name.lower() in {"fxmanifest.lua", "__resource.lua"}:
            # handled later
            continue
        if entry.is_lua:
            src = entry.path.read_text(encoding="utf-8", errors="ignore")
            minified = minify_lua(src)
            rel_str = str(entry.rel_path)
            is_client = rel_str in manifest.client_scripts or rel_str.startswith("client/")
            is_server = rel_str in manifest.server_scripts or rel_str.startswith("server/")
            is_shared = rel_str in manifest.shared_scripts or rel_str.startswith("shared/")
            content = minified.encode("utf-8")
            if is_client or is_shared:
                bundled_client[rel_str] = content
            if is_server or is_shared or (not is_client and not is_shared):
                # default unknown to server too for safety
                bundled_server[rel_str] = content
        else:
            shutil.copy2(entry.path, out_path)

    def build_blob(bundled: dict[str, bytes]) -> bytes:
        toc = {name: len(content) for name, content in bundled.items()}
        concat = b"\n\n--[[BUNDLE_SPLIT]]\n\n".join([bundled[name] for name in sorted(bundled.keys())])
        payload = {
            "toc": toc,
            "files": sorted(bundled.keys()),
        }
        meta = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return crypto.encrypt(meta + b"\n\n--[[META_SPLIT]]\n\n" + concat)

    # Write encrypted blobs to output
    blob_client = build_blob(bundled_client)
    blob_server = build_blob(bundled_server)
    (output_dir / "client.blob").write_bytes(blob_client)
    (output_dir / "server.blob").write_bytes(blob_server)

    # Generate loader files (client and server) and write
    client_loader = generate_loader(blob_filename="client.blob", role="client", license_key_hint=license_key, salt=salt)
    server_loader = generate_loader(blob_filename="server.blob", role="server", license_key_hint=license_key, salt=salt)

    (output_dir / "client.lua").write_text(client_loader, encoding="utf-8")
    (output_dir / "server.lua").write_text(server_loader, encoding="utf-8")

    # Rewrite manifest to point to loaders only, preserve assets
    new_manifest = ManifestData(
        name=manifest.name or output_dir.name,
        version=manifest.version or "1.0.0",
        description=manifest.description or "Locked by fivem-locker",
        author=manifest.author,
        client_scripts=["client.lua"],
        server_scripts=["server.lua"],
        shared_scripts=[],
        files=manifest.files,
        ui_page=manifest.ui_page,
        data_files=manifest.data_files,
        fx_version=manifest.fx_version or "cerulean",
        game=manifest.game or ["gta5"],
    )

    write_manifest(output_dir, new_manifest)

    if verbose:
        print(f"Locked resource written to: {output_dir}")
