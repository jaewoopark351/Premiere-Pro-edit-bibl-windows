from __future__ import annotations

import xml.etree.ElementTree as ET
import urllib.parse
from pathlib import Path
from typing import Any

from ..paths import PathSafetyError, file_uri_to_windows_path


def validate_fcp7_xml_pathurls(
    xml_path: Path,
    *,
    expected_media: Path | None = None,
    expected_clean_audio: Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    pathurl_checks: list[dict[str, Any]] = []
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        return {
            "ok": False,
            "xml": str(xml_path),
            "issues": [f"XML parse failed: {exc}"],
            "pathurls": [],
        }

    file_nodes = root.findall(".//file")
    pathurl_nodes = root.findall(".//pathurl")
    matched_media = False
    matched_clean_audio = expected_clean_audio is None
    file_by_pathurl_id = {id(file_node.find("pathurl")): file_node for file_node in file_nodes if file_node.find("pathurl") is not None}
    for index, pathurl_node in enumerate(pathurl_nodes, 1):
        file_node = file_by_pathurl_id.get(id(pathurl_node))
        raw = pathurl_node.text or ""
        file_id = file_node.attrib.get("id") if file_node is not None else None
        name = file_node.findtext("name") if file_node is not None else None
        check: dict[str, Any] = {
            "index": index,
            "file_id": file_id,
            "name": name,
            "pathurl": raw,
            "is_file_uri": _has_file_scheme(raw),
            "has_backslash_in_uri": "\\" in raw,
        }
        if not check["is_file_uri"]:
            issues.append(f"pathurl is not a file URI: {raw}")
        if check["has_backslash_in_uri"]:
            issues.append(f"pathurl contains backslashes: {raw}")
        try:
            restored = file_uri_to_windows_path(raw)
            check["restored_path"] = str(restored)
            check["exists"] = restored.exists()
            check["is_file"] = restored.is_file()
            if restored.exists() and restored.is_file():
                check["size"] = restored.stat().st_size
            else:
                issues.append(f"pathurl does not resolve to an existing file: {raw} -> {restored}")
            if expected_media is not None and _same_existing_path(restored, expected_media):
                matched_media = True
            if expected_clean_audio is not None and _same_existing_path(restored, expected_clean_audio):
                matched_clean_audio = True
        except (PathSafetyError, OSError, UnicodeError, ValueError) as exc:
            check["restore_error"] = str(exc)
            issues.append(f"pathurl could not be restored to a Windows path: {raw} ({exc})")
        pathurl_checks.append(check)

    if not pathurl_checks:
        issues.append("XML contains no <pathurl> entries.")
    if expected_media is not None and not matched_media:
        issues.append(f"XML does not contain a pathurl for the expected source media: {expected_media.resolve()}")
    if expected_clean_audio is not None and not matched_clean_audio:
        issues.append(f"XML does not contain a pathurl for the expected clean WAV: {expected_clean_audio.resolve()}")

    return {
        "ok": not issues,
        "xml": str(xml_path),
        "issues": issues,
        "pathurls": pathurl_checks,
    }


def validation_error_message(report: dict[str, Any]) -> str:
    lines = [f"FCP7 XML pathurl validation failed: {report.get('xml')}"]
    for issue in report.get("issues", []):
        lines.append(f"- {issue}")
    return "\n".join(lines)


def _same_existing_path(left: Path, right: Path) -> bool:
    try:
        return str(left.resolve()).casefold() == str(right.resolve()).casefold()
    except OSError:
        return str(left).casefold() == str(right).casefold()


def _has_file_scheme(value: str) -> bool:
    return urllib.parse.urlsplit(value).scheme.lower() == "file"
