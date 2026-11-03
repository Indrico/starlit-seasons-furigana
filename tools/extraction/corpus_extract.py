"""Parse Starlit Season's tagged CML DataTables into exact Japanese strings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from asset_extract import Reader


class DataTable:
    def __init__(self, asset: Path):
        self.asset = asset
        r = Reader(asset.read_bytes())
        magic, legacy, legacy_ue3, ue4_version, licensee, custom_count = r.unpack('<Iiiiii')
        if magic != 0x9E2A83C1 or legacy != -7:
            raise ValueError('Unsupported package header')
        r.stream.seek(custom_count * 20, 1)
        header_size, = r.unpack('<i')
        r.fstring()
        flags, name_count, name_offset = r.unpack('<Iii')
        r.stream.seek(name_offset)
        self.names = []
        for _ in range(name_count):
            self.names.append(r.fstring())
            r.stream.read(4)  # serialized case-preserving/non-case-preserving name hashes
        self.r = Reader(asset.with_suffix('.uexp').read_bytes())

    def fname(self):
        index, number = self.r.unpack('<ii')
        if not 0 <= index < len(self.names):
            raise ValueError(f'FName index outside name table at {self.r.stream.tell()-8}')
        value = self.names[index]
        return f'{value}_{number - 1}' if number else value

    def properties(self):
        result = {}
        while True:
            name = self.fname()
            if name == 'None':
                return result
            kind = self.fname()
            size, array_index = self.r.unpack('<ii')
            if not 0 <= size <= 16_000_000:
                raise ValueError(f'Invalid property size for {name}')
            if kind == 'StructProperty':
                self.fname()
                self.r.stream.read(16)
            elif kind in ('ByteProperty', 'EnumProperty', 'ArrayProperty', 'SetProperty'):
                self.fname()
            elif kind == 'MapProperty':
                self.fname()
                self.fname()
            elif kind == 'BoolProperty':
                self.r.stream.read(1)
            guid, = self.r.unpack('<B')
            if guid:
                self.r.stream.read(16)
            raw = self.r.stream.read(size)
            if len(raw) != size:
                raise ValueError(f'Truncated property {name}')
            if kind == 'StrProperty':
                reader = Reader(raw)
                value = reader.fstring()
                if reader.stream.tell() != len(raw):
                    raise ValueError(f'String property has unparsed bytes: {name}')
            else:
                value = {'type': kind, 'raw_hex': raw.hex()}
            result[name] = value

    def rows(self):
        properties = self.properties()
        if 'RowStruct' not in properties:
            raise ValueError('Not a tagged DataTable export')
        # UObject export serialization carries a zero object GUID presence flag.
        guid_present, count = self.r.unpack('<ii')
        if guid_present != 0 or not 0 <= count < 1_000_000:
            raise ValueError('Unsupported DataTable export prefix')
        result = []
        for _ in range(count):
            row_id = self.fname()
            result.append((row_id, self.properties()))
        remaining = self.r.stream.read()
        if remaining not in (b'', b'\xc1\x83\x2a\x9e'):
            raise ValueError(f'Unparsed trailing export bytes: {len(remaining)}')
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tables, records, errors = [], [], []
    for asset in sorted(args.input.rglob('CML*.uasset')):
        if not asset.with_suffix('.uexp').exists():
            continue
        try:
            rows = DataTable(asset).rows()
            logical = str(asset.relative_to(args.input)).replace('\\', '/')
            count = 0
            for row_id, props in rows:
                text = props.get('Japanese')
                if not isinstance(text, str):
                    raise ValueError(f'{row_id} missing Japanese string')
                if not text:
                    continue
                records.append({'asset': logical, 'row_id': row_id,
                                'source_text': text, 'character': props.get('Character', ''),
                                'source_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
                count += 1
            tables.append({'asset': logical, 'rows': len(rows), 'nonempty_japanese': count,
                           'asset_sha256': hashlib.sha256(asset.read_bytes()).hexdigest(),
                           'export_sha256': hashlib.sha256(asset.with_suffix('.uexp').read_bytes()).hexdigest()})
        except Exception as e:
            errors.append({'asset': str(asset), 'error': str(e)})
    with (args.output / 'dialogue.jsonl').open('w', encoding='utf-8', newline='\n') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    report = {'tables_parsed': len(tables), 'records': len(records),
              'distinct_texts': len({r['source_text'] for r in records}),
              'errors': errors, 'tables': tables}
    (args.output / 'corpus-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'tables'}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
