"""Merge private UI localization and verified character names into the corpus.

Inputs and generated exact-source files stay private. Publish only the existing
hash/span export and ui-bindings.lua (hashed texture identities and kana).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from generate import build, hiragana, load_records, lua_string


def compact(value):
    return re.sub(r'\s+', '', value)


def character_readings(profiles, overrides):
    names, aliases, ambiguous = {}, {}, set()
    def add_alias(text, ruby):
        ruby = hiragana(ruby)
        if text in ambiguous:
            return
        if text in aliases and aliases[text] != ruby:
            del aliases[text]
            ambiguous.add(text)
        else:
            aliases[text] = ruby
    verified = {compact(k): compact(v) for k, v in overrides.get('phrases', {}).items()}
    tokens = overrides.get('tokens', {})
    for profile in profiles:
        name = profile.get('Kan_Full', '')
        reading = profile.get('Ruby', '') or verified.get(compact(name), '')
        if not reading:
            reading = tokens.get(name, '')
        if not name or not reading:
            continue
        parts, kana = name.split(), reading.split()
        full = hiragana(compact(reading))
        # Some official overrides have no separating space. Split only using
        # an already verified given-name token, never a tokenizer's name guess.
        if len(parts) == 2 and len(kana) != 2:
            given = hiragana(tokens.get(parts[1], parts[1]))
            if full.endswith(given) and len(full) > len(given):
                kana = [full[:-len(given)], given]
        for separator in ('', ' ', '\u3000'):
            add_alias(separator.join(parts), separator.join(kana) if len(kana) == len(parts) else full)
        if len(parts) == len(kana):
            for part, ruby in zip(parts, kana):
                add_alias(part, ruby)
        names[profile['row_id']] = full
    return names, aliases


def prepare(dialogue, localization, profiles, overrides):
    names, aliases = character_readings(profiles, overrides)
    merged = dict(overrides)
    # Short aliases are exact-source corrections. Treating a one-character
    # person's name as a phrase would change unrelated words in dialogue.
    merged['exact'] = {**overrides.get('exact', {}), **aliases}
    records = list(dialogue)
    for entry in localization:
        text = entry.get('text', '')
        if text:
            records.append({'source_text': text})
    records.extend({'source_text': text} for text in aliases)
    return records, merged, names


def image_bindings(names, geometry=None):
    # Only texture families present in the local asset inventory. No source
    # texture, character name, asset path, or table row is copied to the export.
    result = {}
    for identity, reading in names.items():
        for template in ('WDT_name_{}', 'WDT_DLC_name_{}', 'WT_s4u_wipe_Capture1_name_jp_{}'):
            key = hashlib.sha256(template.format(identity).lower().encode()).hexdigest()
            if geometry is None or key in geometry:
                bounds = {'left': 0, 'right': 1, 'top': 0}
                for field in bounds:
                    value = (geometry or {}).get(key, {}).get(field, bounds[field])
                    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                        raise ValueError('Image bounds must be finite normalized coordinates')
                    bounds[field] = value
                if bounds['left'] >= bounds['right']:
                    raise ValueError('Image ink bounds must have positive width')
                result[key] = {'reading': reading, **bounds}
    return result


def write_bindings(path, bindings, aliases=()):
    with Path(path).open('w', encoding='utf-8', newline='\n') as out:
        out.write('-- Kana-only image annotations and verified exact-name identities.\nreturn {images={\n')
        for key, value in sorted(bindings.items()):
            out.write(f'[{lua_string(key)}]={{reading={lua_string(value["reading"])},'
                      f'left={value["left"]},right={value["right"]},top={value.get("top", 0)}}},\n')
        out.write('},names={\n')
        for text in sorted(aliases):
            key = hashlib.sha256(text.encode()).hexdigest()
            out.write(f'["{key}"]=true,\n')
        out.write('}}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dialogue', type=Path, required=True)
    parser.add_argument('--localization', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--overrides', type=Path, default=Path(__file__).with_name('overrides.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image-geometry', type=Path, help='Hash-keyed normalized ink bounds from local textures')
    args = parser.parse_args()
    records, overrides, names = prepare(load_records(args.dialogue),
        json.loads(args.localization.read_text(encoding='utf-8')),
        json.loads(args.profiles.read_text(encoding='utf-8')),
        json.loads(args.overrides.read_text(encoding='utf-8')))
    report = build(records, args.output, overrides)
    bindings = image_bindings(names, json.loads(args.image_geometry.read_text(encoding='utf-8')) if args.image_geometry else None)
    write_bindings(args.output / 'ui-bindings.lua', bindings, overrides['exact'])
    report.update(verified_character_identities=len(names), image_bindings=len(bindings))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
