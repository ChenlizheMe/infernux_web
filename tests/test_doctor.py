from __future__ import annotations

import json

import pytest

from infernux_web.native_payload import inspect_player_payload


def test_player_doctor_explains_stale_manifest_without_python_runtime(tmp_path):
    player = tmp_path / "player"
    player.mkdir()
    (player / "Player.inxmanifest").write_text(
        json.dumps(
            {
                "$schema": "infernux.web_player",
                "engine": "0.4.0",
                "platform": "web",
                "architecture": "wasm32",
                "python_abi": "cp313",
                "configuration": "Release",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stale/out-of-source") as error:
        inspect_player_payload(player, engine="0.4.0")

    message = str(error.value)
    assert "python_runtime" in message
    assert "publish/player" in message
