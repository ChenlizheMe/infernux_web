"""Check the installed Web payload, without looking for a compiler or checkout."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from Infernux.engine.build import (
    BuildDiagnostic, BuildTargetId, CapabilityReport, DiagnosticSeverity,
)
from Infernux.version import ENGINE_VERSION

from .native_payload import inspect_player_payload, inspect_shader_tools


def inspect_web_toolchain(target: BuildTargetId | str) -> CapabilityReport:
    root = Path(__file__).resolve().parent
    details: dict[str, object] = {"target": str(target), "player_root": str(root / "player")}
    try:
        if sys.platform not in {"win32", "linux"} or platform.machine().lower() not in {
            "amd64", "x86_64",
        }:
            raise ValueError("The Web plugin requires a Windows or Linux x64 editor")
        host = "windows-x64" if sys.platform == "win32" else "linux-x64"
        details["player"] = inspect_player_payload(root / "player", engine=ENGINE_VERSION)
        details.update(inspect_shader_tools(root / "tools", host=host))
    except (OSError, ValueError) as error:
        return CapabilityReport(False, (
            BuildDiagnostic(
                DiagnosticSeverity.ERROR, "web.player.payload", str(error),
                source="infernux/platform-web",
            ),
        ), details)
    return CapabilityReport(True, (), details)


__all__ = ["inspect_web_toolchain"]
