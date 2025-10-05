from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .crypto import encrypt_xor_stream, b64_encode


MANIFEST_FILES = ("fxmanifest.lua", "__resource.lua")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_manifest(manifest_path: Path) -> Dict[str, List[str]]:
    """
    Very tolerant parser for fxmanifest/__resource that extracts client/server/shared script lists.
    Supports forms:
      client_script 'file.lua'
      client_script "file.lua"
      client_scripts { 'a.lua', 'b.lua' }
    Returns dict: {"client": [...], "server": [...], "shared": [...], "lua54": "yes"|"no"|None, "fx_version": str|None }
    Paths are returned as-is (relative).
    """
    text = _read_text(manifest_path)

    def extract_list(single_pat: str, multi_pat: str) -> List[str]:
        results: List[str] = []
        # Single entry
        for m in re.finditer(single_pat, text, flags=re.IGNORECASE):
            results.append(m.group(1))
        # Multi entry { ... }
        for m in re.finditer(multi_pat, text, flags=re.IGNORECASE | re.DOTALL):
            body = m.group(1)
            for sm in re.finditer(r"['\"]([^'\"]+)['\"]", body):
                results.append(sm.group(1))
        return results

    client = extract_list(
        r"client_script\s+['\"]([^'\"]+)['\"]",
        r"client_scripts\s*\{([^}]*)\}",
    )
    server = extract_list(
        r"server_script\s+['\"]([^'\"]+)['\"]",
        r"server_scripts\s*\{([^}]*)\}",
    )
    shared = extract_list(
        r"shared_script\s+['\"]([^'\"]+)['\"]",
        r"shared_scripts\s*\{([^}]*)\}",
    )

    lua54_match = re.search(r"lua54\s+['\"]?(yes|no)['\"]?", text, flags=re.IGNORECASE)
    lua54 = lua54_match.group(1).lower() if lua54_match else None

    fx_version_match = re.search(r"fx_version\s+['\"]?([\w-]+)['\"]?", text, flags=re.IGNORECASE)
    fx_version = fx_version_match.group(1) if fx_version_match else None

    return {
        "client": client,
        "server": server,
        "shared": shared,
        "lua54": lua54,
        "fx_version": fx_version,
    }


def _gather_files(resource_dir: Path, rel_paths: List[str]) -> List[Path]:
    files: List[Path] = []
    for rel in rel_paths:
        # Support globs in manifest entries
        matches = list(resource_dir.glob(rel))
        if matches:
            for m in matches:
                if m.is_file() and m.suffix.lower() == ".lua":
                    files.append(m)
            continue
        p = resource_dir / rel
        if p.is_file() and p.suffix.lower() == ".lua":
            files.append(p)
    # Deduplicate while preserving order
    seen = set()
    unique: List[Path] = []
    for p in files:
        rp = p.relative_to(resource_dir).as_posix()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
    return unique


def _build_bundle_blob(resource_dir: Path, file_paths: List[Path]) -> bytes:
    """
    Build a compact length-prefixed blob for file table:
      header: b"FLOK1\n"
      N:<num>\n
      For each entry:
        P:<path_len>\n
        <path_bytes>
        C:<code_len>\n
        <code_bytes>
    """
    header = b"FLOK1\n"
    out = bytearray()
    out += header
    out += f"N:{len(file_paths)}\n".encode("utf-8")
    for p in file_paths:
        rel = p.relative_to(resource_dir).as_posix().encode("utf-8")
        code = p.read_bytes()
        out += f"P:{len(rel)}\n".encode("utf-8")
        out += rel
        out += f"C:{len(code)}\n".encode("utf-8")
        out += code
    return bytes(out)


def _write_manifest(out_dir: Path, *, fx_version: Optional[str], lua54: Optional[str], client_bundle: Optional[str], server_bundle: Optional[str]) -> None:
    lines: List[str] = []
    lines.append("fx_version 'cerulean'" if not fx_version else f"fx_version '{fx_version}'")
    lines.append("game 'gta5'")
    if lua54 is None:
        lines.append("lua54 'yes'")
    else:
        lines.append(f"lua54 '{lua54}'")
    files: List[str] = []
    if client_bundle:
        lines.append("client_scripts { 'loader_client.lua' }")
        files.append(client_bundle)
    if server_bundle:
        lines.append("server_scripts { 'loader_server.lua' }")
        files.append(server_bundle)
    if files:
        files_list = ", ".join(f"'{f}'" for f in files)
        lines.append(f"files {{ {files_list} }}")
    out = "\n".join(lines) + "\n"
    (out_dir / "fxmanifest.lua").write_text(out, encoding="utf-8")


def _load_loader_template() -> str:
    tpl_path = Path(__file__).with_name("loader_template.lua")
    return tpl_path.read_text(encoding="utf-8")


def _render_loader(side: str, key: str, bundle_filename: str) -> str:
    tpl = _load_loader_template()
    return (
        tpl.replace("__SIDE__", side)
        .replace("__KEY_LITERAL__", json.dumps(key))
        .replace("__BUNDLE_FILENAME__", json.dumps(bundle_filename))
    )


def pack_resource(resource_dir: str, out_dir: str, *, key: Optional[str], include_client: bool, include_server: bool) -> Dict[str, str]:
    rdir = Path(resource_dir)
    if not rdir.exists():
        raise FileNotFoundError(f"resource dir not found: {resource_dir}")

    manifest_path = None
    for mf in MANIFEST_FILES:
        p = rdir / mf
        if p.exists():
            manifest_path = p
            break
    if not manifest_path:
        raise FileNotFoundError("No fxmanifest.lua or __resource.lua found in resource directory")

    meta = _parse_manifest(manifest_path)
    client_files = _gather_files(rdir, meta["client"]) + _gather_files(rdir, meta["shared"]) if include_client else []
    server_files = _gather_files(rdir, meta["server"]) + _gather_files(rdir, meta["shared"]) if include_server else []

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    key_str = key or os.urandom(16).hex()
    key_bytes = key_str.encode("utf-8")

    client_bundle_name = None
    server_bundle_name = None

    if client_files:
        client_blob = _build_bundle_blob(rdir, client_files)
        client_encrypted = encrypt_xor_stream(client_blob, key_bytes, side_tag="client")
        client_b64 = b64_encode(client_encrypted)
        client_bundle_name = "bundle_client.b64"
        (out / client_bundle_name).write_text(client_b64, encoding="utf-8")
        loader_client = _render_loader("client", key_str, client_bundle_name)
        (out / "loader_client.lua").write_text(loader_client, encoding="utf-8")

    if server_files:
        server_blob = _build_bundle_blob(rdir, server_files)
        server_encrypted = encrypt_xor_stream(server_blob, key_bytes, side_tag="server")
        server_b64 = b64_encode(server_encrypted)
        server_bundle_name = "bundle_server.b64"
        (out / server_bundle_name).write_text(server_b64, encoding="utf-8")
        loader_server = _render_loader("server", key_str, server_bundle_name)
        (out / "loader_server.lua").write_text(loader_server, encoding="utf-8")

    _write_manifest(out, fx_version=meta.get("fx_version"), lua54=meta.get("lua54"), client_bundle=client_bundle_name, server_bundle=server_bundle_name)

    guidance = {
        "key": key_str,
        "resource_out": str(out),
        "client_bundle": client_bundle_name or "",
        "server_bundle": server_bundle_name or "",
    }
    (out / "LOCKER_INFO.txt").write_text(
        "FiveM Locker\n" + json.dumps(guidance, indent=2), encoding="utf-8"
    )
    return guidance
