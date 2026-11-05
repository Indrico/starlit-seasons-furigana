"""Export only hashed, normalized ink bounds for local Japanese name textures."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

from PIL import Image
from asset_extract import Pak


def ink_bounds(data):
    """Read the first inline mip in this build's cooked UI texture exports."""
    for pixel_format in (b'PF_BC7\0', b'PF_B8G8R8A8\0'):
        offset = data.find(pixel_format)
        if offset >= 16:
            break
    else:
        return None
    width, height, depth, length = struct.unpack_from('<4i', data, offset - 16)
    if not (0 < width <= 8192 and 0 < height <= 8192 and depth == 1 and length == len(pixel_format)):
        raise ValueError('Unsupported texture dimensions or platform header')
    mip = offset + len(pixel_format) + 12
    flags, count, size, _ = struct.unpack_from('<IIIQ', data, mip)
    expected = ((width+3)//4)*((height+3)//4)*16 if pixel_format == b'PF_BC7\0' else width*height*4
    if flags != 0x48 or count != size or size != expected or mip+20+size > len(data):
        raise ValueError('Unsupported non-inline or truncated UI texture mip')
    raw = data[mip+20:mip+20+size]
    if pixel_format == b'PF_BC7\0':
        header = struct.pack('<7I11I', 124, 0x81007, height, width, size, 0, 1, *([0]*11))
        pixel = struct.pack('<II4s5I', 32, 4, b'DX10', 0, 0, 0, 0, 0)
        caps = struct.pack('<5I', 0x1000, 0, 0, 0, 0) + struct.pack('<5I', 98, 3, 0, 1, 0)
        image = Image.open(io.BytesIO(b'DDS '+header+pixel+caps+raw)).convert('RGBA')
    else:
        image = Image.frombytes('RGBA', (width, height), raw, 'raw', 'BGRA')
    bounds = image.getchannel('A').point(lambda alpha: 255 if alpha > 128 else 0).getbbox()
    if bounds is None:
        return None
    left, top, right, _ = bounds
    return {'left': round(left/width, 5), 'right': round(right/width, 5), 'top': round(top/height, 5)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = bytes.fromhex(args.key_file.read_text().strip())
    result = {}
    for archive in sorted((args.game/'StarlitSeason/Content/Paks').glob('pakchunk*-WindowsNoEditor.pak')):
        pak = Pak(archive, key)
        for entry in pak.entries:
            path = entry.path.lower()
            basename = Path(path).stem
            if '/l10n/' in path or not path.endswith('.uexp') or not basename.startswith(
                    ('wdt_name_', 'wdt_dlc_name_', 'wt_s4u_wipe_capture1_name_jp_')):
                continue
            bounds = ink_bounds(pak.read(entry))
            if bounds is not None:
                result[hashlib.sha256(basename.encode()).hexdigest()] = bounds
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({'calibrated_texture_identities': len(result)}))


if __name__ == '__main__':
    main()
