"""Read UE4 compact JA LocRes resources and resolve profile name keys.

Layout reference: CUE4Parse FTextLocalizationResource/FTextKey (upstream).
"""
import argparse
import json
from pathlib import Path

from asset_extract import Reader
from corpus_extract import DataTable


def read_locres(path):
    r = Reader(path.read_bytes())
    if r.stream.read(16) != bytes.fromhex('0e147475674a03fc4a15909dc3377f1b'):
        raise ValueError('Invalid LocRes magic')
    version, = r.unpack('<B')
    if version not in (1, 2):
        raise ValueError(f'Unsupported LocRes version {version}')
    offset, = r.unpack('<q')
    entry_offset = r.stream.tell()
    r.stream.seek(offset)
    count, = r.unpack('<i')
    strings = []
    for _ in range(count):
        strings.append(r.fstring())
        if version >= 2:
            r.unpack('<i')  # reference count
    if r.stream.read():
        raise ValueError('Trailing bytes in localized string array')
    r.stream.seek(entry_offset)
    if version >= 2:
        expected_entries, = r.unpack('<i')
    namespace_count, = r.unpack('<i')
    entries = []
    for _ in range(namespace_count):
        if version >= 2:
            r.unpack('<I')
        namespace = r.fstring()
        key_count, = r.unpack('<i')
        for _ in range(key_count):
            if version >= 2:
                r.unpack('<I')
            key = r.fstring()
            source_hash, index = r.unpack('<Ii')
            entries.append({'namespace': namespace, 'key': key,
                            'source_hash': source_hash, 'text': strings[index]})
    if r.stream.tell() != offset or (version >= 2 and len(entries) != expected_entries):
        raise ValueError('LocRes table boundary/count mismatch')
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--content', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(args.content.rglob('*.locres')):
        for entry in read_locres(path):
            entry['resource'] = str(path.relative_to(args.content)).replace('\\', '/')
            entries.append(entry)
    (args.output / 'localization-ja.json').write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    by_key = {entry['key']: entry['text'] for entry in entries}
    profiles = []
    for row_id, fields in DataTable(args.content / 'MD/MD_Character_Profile.uasset').rows():
        profiles.append({'row_id': row_id, **{
            k: by_key.get(v, v) if isinstance(v, str) else v for k, v in fields.items()}})
    (args.output / 'character-profiles-resolved.json').write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'localization_entries': len(entries), 'character_profiles': len(profiles)}))


if __name__ == '__main__':
    main()
