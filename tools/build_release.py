"""Build a drag-and-drop release from a pinned loader and private reading input."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

import install_mod
from readings.export_annotations import annotations, write_lua


ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v0.3.0-alpha.2'


def build(loader_zip, readings_json, output, native_dll, ui_bindings=None):
    database = annotations(json.loads(Path(readings_json).read_text(encoding='utf-8')))
    if not database['entries']:
        raise ValueError('The release needs prebuilt annotations')
    with tempfile.TemporaryDirectory(prefix='starlit-release-') as folder:
        reading_file = Path(folder) / 'readings.lua'
        write_lua(reading_file, database)
        files = install_mod._inputs(Path(loader_zip), reading_file, Path(native_dll), ui_bindings)
    with zipfile.ZipFile(loader_zip) as loader:
        license_bytes = loader.read('ue4ss/LICENSE')
    files[f'{install_mod.BIN_REL}/ue4ss/LICENSE'] = license_bytes
    manifest = {
        'version': 1, 'release': VERSION,
        'shipping_sha256': install_mod.EXPECTED_SHIPPING_SHA256,
        'loader_zip_sha256': install_mod.EXPECTED_LOADER_SHA256,
        'annotation_format': database['format'], 'annotated_texts': len(database['entries']),
        'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())],
    }
    files['StarlitFurigana/manifest.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    files['StarlitFurigana/manage.ps1'] = (ROOT / 'portable/manage.ps1').read_bytes()
    for name in ['Check-Furigana.cmd', 'Uninstall-Furigana.cmd', 'README-FURIGANA.txt']:
        data = (ROOT / 'portable' / name).read_bytes()
        if name.endswith('.cmd'):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        files[name] = data
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError('Refusing to overwrite an existing release ZIP')
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in sorted(files.items()):
            member = zipfile.ZipInfo(name)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            package.writestr(member, data, compresslevel=9)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader-zip', required=True, type=Path)
    parser.add_argument('--readings-json', required=True, type=Path)
    parser.add_argument('--native-dll', required=True, type=Path)
    parser.add_argument('--ui-bindings', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = build(args.loader_zip, args.readings_json, args.output, args.native_dll, args.ui_bindings)
    print(json.dumps({'release': VERSION, 'files': len(manifest['files']),
                      'annotated_texts': manifest['annotated_texts'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
