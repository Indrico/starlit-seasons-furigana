"""Extract the installed original dialogue and its rendering resources."""
import argparse
import json
from pathlib import Path

from asset_extract import Pak


def selected(path):
    return ('/Commu/Localize/' in path or '/Widget/Commu/' in path
            or '/Widget/Font/' in path or '/MD/MD_Character_Profile.' in path
            or ('/Localization/' in path and '/ja/' in path and path.endswith('.locres')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    key = bytes.fromhex(args.key_file.read_text().strip())
    archives = sorted((args.game / 'StarlitSeason/Content/Paks').glob('pakchunk*-WindowsNoEditor.pak'))
    if not archives:
        raise SystemExit('No original PAK archives found')
    for archive in archives:
        pak = Pak(archive, key)
        mount = pak.mount.removeprefix('../../../')
        paths = []
        for entry in pak.entries:
            full = mount + entry.path
            if selected(full):
                target = (destination / full).resolve()
                if destination not in target.parents:
                    raise ValueError(f'Unsafe asset path: {full}')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(pak.read(entry))
                paths.append(full)
        stat = archive.stat()
        manifest = {'pak': str(archive.resolve()), 'pak_size': stat.st_size,
                    'pak_mtime_ns': stat.st_mtime_ns, 'version': pak.version,
                    'mount': pak.mount, 'index_sha1_verified': True,
                    'index_sha1': pak.index_sha1, 'total': len(pak.entries),
                    'selected_entries': paths, 'all_paths': [e.path for e in pak.entries]}
        (destination / (archive.stem + '-manifest.json')).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'pak': archive.name, 'total': len(pak.entries),
                          'extracted': len(paths)}), flush=True)


if __name__ == '__main__':
    main()
