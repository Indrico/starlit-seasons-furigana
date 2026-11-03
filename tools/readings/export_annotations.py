"""Export prebuilt kana annotations without copying original dialogue text."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def annotations(records):
    entries = {}
    for record in records:
        source = record['source_text']
        segments = record['segments']
        if ''.join(segment['base'] for segment in segments) != source:
            raise ValueError('Reading segments do not reconstruct their source')
        if not any(segment.get('reading') for segment in segments):
            continue
        spans, cursor = [], 1
        for segment in segments:
            length = len(segment['base'].encode('utf-8'))
            reading = segment.get('reading')
            if reading:
                if segment.get('control') or not re.fullmatch('[ぁ-ゖーゝゞ]+', reading):
                    raise ValueError('Release readings must contain kana only')
                if not length:
                    raise ValueError('An annotation cannot have an empty base')
                spans.append([cursor, length, reading])
            elif segment.get('control') and length:
                spans.append([cursor, length, False])
            cursor += length
        key = hashlib.sha256(source.encode('utf-8')).hexdigest()
        entry = {'n': cursor - 1, 's': spans}
        if key in entries and entries[key] != entry:
            raise ValueError('Conflicting annotations for an identical source hash')
        entries[key] = entry
    return {'format': 'starlit-furigana-spans-v1', 'entries': entries}


def write_lua(path, database):
    with Path(path).open('w', encoding='utf-8', newline='\n') as output:
        output.write('-- Prebuilt kana annotations; source dialogue is read from the game.\n')
        output.write('return {format="starlit-furigana-spans-v1",entries={\n')
        for key, entry in sorted(database['entries'].items()):
            output.write(f'["{key}"]={{n={entry["n"]},s={{')
            for first, length, reading in entry['s']:
                value = 'false' if reading is False else json.dumps(reading, ensure_ascii=False)
                output.write(f'{{{first},{length},{value}}},')
            output.write('}},\n')
        output.write('}}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readings_json', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    database = annotations(json.loads(args.readings_json.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_lua(args.output, database)
    print(json.dumps({'format': database['format'], 'annotated_texts': len(database['entries'])}))


if __name__ == '__main__':
    main()
