from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ManifestData:
    name: str | None = None
    version: str | None = None
    description: str | None = None
    author: str | None = None
    client_scripts: list[str] = field(default_factory=list)
    server_scripts: list[str] = field(default_factory=list)
    shared_scripts: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    ui_page: str | None = None
    data_files: list[tuple[str, str]] = field(default_factory=list)
    fx_version: str | None = None
    game: list[str] | None = None


def read_manifest(root: Path) -> ManifestData:
    mf = root / "fxmanifest.lua"
    if not mf.exists():
        mf = root / "__resource.lua"
    if not mf.exists():
        return ManifestData()

    text = mf.read_text(encoding="utf-8", errors="ignore")
    data = ManifestData()

    import re

    def _extract_block_list(keyword: str) -> list[str]:
        pattern = re.compile(re.escape(keyword) + r"\s*\{([^\}]*)\}", re.S)
        m = pattern.search(text)
        if not m:
            return []
        body = m.group(1)
        items: list[str] = []
        for line in body.splitlines():
            line = line.strip().strip(",").strip()
            if not line:
                continue
            if (line.startswith("'") and line.endswith("'")) or (line.startswith('"') and line.endswith('"')):
                items.append(line[1:-1])
        return items

    def _extract_single_lines(keyword: str) -> list[str]:
        pattern = re.compile(re.escape(keyword) + r"\s+(['\"])(.+?)\1")
        return [m.group(2) for m in pattern.finditer(text)]

    data.files = _extract_block_list("files")
    data.client_scripts = _extract_block_list("client_scripts") or _extract_single_lines("client_script")
    data.server_scripts = _extract_block_list("server_scripts") or _extract_single_lines("server_script")
    data.shared_scripts = _extract_block_list("shared_scripts") or _extract_single_lines("shared_script")

    m = re.search(r"ui_page\s+['\"](.*?)['\"]", text)
    if m:
        data.ui_page = m.group(1)

    m = re.search(r"fx_version\s+['\"](.*?)['\"]", text)
    if m:
        data.fx_version = m.group(1)

    games = re.findall(r"game\s*\{([^\}]*)\}", text, re.S)
    if games:
        g_list: list[str] = []
        for part in games[0].split(','):
            p = part.strip().strip("'").strip('"').strip()
            if p:
                g_list.append(p)
        data.game = g_list or None

    m = re.search(r"(?m)^\s*name\s+['\"](.*?)['\"]", text)
    if m:
        data.name = m.group(1)
    m = re.search(r"(?m)^\s*version\s+['\"](.*?)['\"]", text)
    if m:
        data.version = m.group(1)
    m = re.search(r"(?m)^\s*description\s+['\"](.*?)['\"]", text)
    if m:
        data.description = m.group(1)
    m = re.search(r"(?m)^\s*author\s+['\"](.*?)['\"]", text)
    if m:
        data.author = m.group(1)

    return data


def write_manifest(root: Path, manifest: ManifestData) -> None:
    out: list[str] = []
    out.append(f"fx_version '{manifest.fx_version or 'cerulean'}'")
    if manifest.game:
        games = ", ".join(f"'{g}'" for g in manifest.game)
        out.append(f"game {{ {games} }}")

    if manifest.name:
        out.append(f"name '{manifest.name}'")
    if manifest.version:
        out.append(f"version '{manifest.version}'")
    if manifest.description:
        out.append(f"description '{manifest.description}'")
    if manifest.author:
        out.append(f"author '{manifest.author}'")

    if manifest.ui_page:
        out.append(f"ui_page '{manifest.ui_page}'")

    if manifest.files:
        files_joined = ",\n  ".join(f"'{f}'" for f in manifest.files)
        out.append("files {\n  " + files_joined + "\n}")

    if manifest.client_scripts:
        cs = ", ".join(f"'{f}'" for f in manifest.client_scripts)
        out.append(f"client_scripts {{ {cs} }}")

    if manifest.server_scripts:
        ss = ", ".join(f"'{f}'" for f in manifest.server_scripts)
        out.append(f"server_scripts {{ {ss} }}")

    if manifest.shared_scripts:
        sh = ", ".join(f"'{f}'" for f in manifest.shared_scripts)
        out.append(f"shared_scripts {{ {sh} }}")

    if manifest.data_files:
        for t, p in manifest.data_files:
            out.append(f"data_file '{t}' '{p}'")

    (root / "fxmanifest.lua").write_text("\n".join(out) + "\n", encoding="utf-8")
