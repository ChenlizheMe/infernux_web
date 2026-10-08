"""UI shaders consume the sealed GUID closure, independent of authoring roots."""

import json
from pathlib import Path

import pytest

from infernux.lib import _Infernux as native
from infernux.engine.player_package_native import write_pack
from infernux_web.exporter import _stage_web_ui_shader_sources


@pytest.fixture(scope='module', autouse=True)
def shader_host(tmp_path_factory):
    from infernux.lib import Infernux, LogLevel, RuntimeMode, lib_dir
    from infernux.resources import resources_path

    host = Infernux(lib_dir, RuntimeMode.Headless)
    host.set_log_level(LogLevel.Warn)
    host.init_headless(str(tmp_path_factory.mktemp('ui_shader_host')), resources_path)
    try:
        yield host
    finally:
        host.exit()


def _content(tmp_path, roots, *, fault=None, builtin_material=False):
    data = tmp_path / 'staged/Game_Data'
    data.mkdir(parents=True)
    files = tmp_path / 'sealed'
    files.mkdir()
    artifacts, records, pairs = [], [], []
    for suffix, guid, root, stage in zip(
        ('.vert', '.frag', '.mat'), ('a' * 32, 'b' * 32, 'c' * 32), roots,
        ('vertex', 'fragment', 'material'),
    ):
        path = root + '/Screen' + suffix
        artifact_path = path if suffix != '.mat' else 'Library/Artifacts/Document/' + guid + '.inxdoc'
        if suffix == '.mat' and builtin_material:
            path = 'Library/Resources/materials/Screen.mat'
            artifact_path = 'infernux/resources/materials/Screen.mat'
        artifact_id = 'artifact:' + guid
        metadata = {'file_path': {'value': 'Z:/obsolete/absolute/authoring/path'}}
        if suffix == '.mat':
            stages = {'vertex': {'guid': 'a' * 32, 'shader_id': 'Screen'},
                      'fragment': {'guid': 'b' * 32, 'shader_id': 'Screen'}}
            if fault == 'missing-stage':
                stages['fragment']['guid'] = 'd' * 32
            if fault == 'wrong-identity':
                stages['fragment']['shader_id'] = 'Other'
            payload = (json.dumps({'shaders': stages}).encode() if builtin_material
                       else native._encode_asset_document({'shaders': stages}))
        else:
            domain = 'WorldUI' if fault == 'cross-domain' and stage == 'fragment' else 'ScreenUI'
            properties = [{'name': 'extraColor', 'type': 'Color'}] if fault == 'properties' and stage == 'fragment' else []
            metadata.update(shader_id={'value': 'Screen'}, shader_capabilities={'value': json.dumps([domain])},
                            properties={'value': json.dumps(properties)})
            source = (Path(__file__).parent / 'fixtures/ui_material' / ('Screen' + suffix)).read_text(encoding='utf-8')
            payload = source.replace('Capabilities [ScreenUI]', f'Capabilities [{domain}]').encode()
        source = files / (guid + suffix)
        source.write_bytes(payload)
        pairs.append((artifact_path, source))
        artifacts.append(dict(runtime_artifact_id=artifact_id, runtime_path=artifact_path,
                              package='Game_Data/Content.inxpkg', asset_guid=guid, dependencies=[]))
        records.append(dict(guid=guid, runtime_path=path, primary_runtime_artifact_id=artifact_id,
                            runtime_artifact_ids=[artifact_id], dependencies=[], metadata={'metadata': metadata}))
    record_file = files / 'RuntimeAssetRecords.json'
    record_file.write_text(json.dumps({'entries': records}), encoding='utf-8')
    pairs.append(('Library/RuntimeAssetRecords.json', record_file))
    artifacts.append(dict(runtime_artifact_id='records', runtime_path='Library/RuntimeAssetRecords.json',
                          package='Game_Data/Content.inxpkg', dependencies=[]))
    write_pack(pairs, data / 'Content.inxpkg')
    catalog = files / 'RuntimeAssetCatalog.json'
    catalog.write_text(json.dumps({'artifacts': artifacts}), encoding='utf-8')
    write_pack([('RuntimeAssetCatalog.json', catalog)], data / 'AssetCatalog.inxcat')
    return data


@pytest.mark.parametrize('roots', [
    ('Assets', 'Assets', 'Assets'),
    ('Packages/team/ui/runtime',) * 3,
    ('Assets', 'Assets', 'Packages/team/ui/runtime'),
    ('Assets', 'Packages/team/ui/runtime', 'Assets'),
])
@pytest.mark.parametrize('builtin_material', [False, True])
def test_ui_shader_cook_uses_only_sealed_guid_closure(tmp_path, roots, builtin_material):
    data = _content(tmp_path, roots, builtin_material=builtin_material)
    # These authoring files are deliberately invalid and absent from the cook.
    # Neither disabled packages nor changes after cook may affect translation.
    for root in ('Assets', 'Packages/disabled/runtime'):
        path = tmp_path / root
        path.mkdir(parents=True)
        (path / 'Broken.mat').write_text('invalid material', encoding='utf-8')
        (path / 'Broken.frag.meta').write_text('invalid metadata', encoding='utf-8')
    relocated = tmp_path / '中文 空格 & moved player'
    data.parent.rename(relocated)
    data = relocated / 'Game_Data'
    cook = tmp_path / 'cook'
    cook.mkdir()
    entries = []
    _stage_web_ui_shader_sources(data, cook, entries, native)
    assert {(entry['name'], entry['stage']) for entry in entries} == {('Screen', 'vertex'), ('Screen', 'fragment')}
    for entry in entries:
        text = (cook / entry['source']).read_text(encoding='utf-8')
        assert 'void main()' in text
        assert 'ShaderInfo' not in text
    compiled = native._compile_graphics_glsl_batch(
        {entry['stage']: (cook / entry['source']).read_text(encoding='utf-8') for entry in entries},
        'sealed-ui-stage-test',
    )
    assert all(compiled[stage] for stage in ('vertex', 'fragment'))


@pytest.mark.parametrize('fault, message', [
    ('cross-domain', 'domains disagree'),
    ('properties', 'material descriptor ABI'),
    ('missing-stage', 'incomplete shader GUID pair'),
    ('wrong-identity', 'shader identity changed'),
])
def test_ui_shader_cook_rejects_invalid_material_contract(tmp_path, fault, message):
    data = _content(tmp_path, ('Assets',) * 3, fault=fault)
    cook = tmp_path / 'cook'
    cook.mkdir()
    with pytest.raises(ValueError, match=message):
        _stage_web_ui_shader_sources(data, cook, [], native)
