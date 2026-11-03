"""Read local UE4 PAK archives and extract selected original resources.

This utility never writes into the game's Content or Binaries directories.
PAK v3 and v8 legacy directory indexes are supported. Keys are validated by
the index SHA1 before any extraction is attempted.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha1
import io
import json
from pathlib import Path
import struct
import zlib

from Crypto.Cipher import AES


class Reader:
    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)

    def unpack(self, fmt):
        return struct.unpack(fmt, self.stream.read(struct.calcsize(fmt)))

    def fstring(self):
        n, = self.unpack('<i')
        if not n:
            return ''
        if abs(n) > 1_000_000:
            raise ValueError(f'Implausible FString length {n}')
        raw = self.stream.read(abs(n) * (2 if n < 0 else 1))
        return raw.decode('utf-16-le' if n < 0 else 'utf-8').rstrip('\0')


@dataclass
class Entry:
    path: str
    offset: int
    compressed_size: int
    size: int
    compression: int
    digest: bytes
    blocks: list
    flags: int
    block_size: int
    header_size: int


class Pak:
    def __init__(self, path: Path, key: bytes | None = None):
        self.path = path
        self.key = key
        with path.open('rb') as f:
            f.seek(-min(4096, path.stat().st_size), 2)
            tail = f.read()
            pos = tail.rfind(b'\xe1\x12\x6f\x5a')
            if pos < 0:
                raise ValueError('PAK footer not found')
            self.version, offset, size = struct.unpack_from('<iqq', tail, pos + 4)
            if self.version not in (3, 8):
                raise ValueError(f'Unsupported PAK version {self.version}')
            self.encrypted_index = self.version >= 4 and bool(tail[pos - 1])
            digest = tail[pos + 24:pos + 44]
            self.index_sha1 = digest.hex()
            f.seek(offset)
            index = f.read(size)
        if self.encrypted_index:
            if key is None:
                raise ValueError('AES key required')
            index = AES.new(key, AES.MODE_ECB).decrypt(index)
        if sha1(index).digest() != digest:
            raise ValueError('PAK index SHA1 mismatch: wrong key or unsupported format')
        r = Reader(index)
        self.mount = r.fstring()
        count, = r.unpack('<i')
        self.entries = []
        for _ in range(count):
            name = r.fstring()
            entry_start = r.stream.tell()
            off, compressed, size, method = r.unpack('<qqqI')
            checksum = r.stream.read(20)
            blocks = []
            if method:
                block_count, = r.unpack('<i')
                blocks = [r.unpack('<qq') for _ in range(block_count)]
            flags, block_size = r.unpack('<BI')
            header_size = r.stream.tell() - entry_start
            self.entries.append(Entry(name, off, compressed, size, method,
                                      checksum, blocks, flags, block_size, header_size))

    def read(self, entry: Entry) -> bytes:
        with self.path.open('rb') as f:
            if entry.compression:
                parts = []
                for begin, end in entry.blocks:
                    length = end - begin
                    begin += entry.offset if self.version >= 5 else 0
                    f.seek(begin)
                    raw = f.read((length + 15) // 16 * 16 if entry.flags & 1 else length)
                    if entry.flags & 1:
                        raw = AES.new(self.key, AES.MODE_ECB).decrypt(raw)[:length]
                    if entry.compression != 1:
                        raise ValueError(f'Unsupported compression {entry.compression}')
                    parts.append(zlib.decompress(raw))
                result = b''.join(parts)
            else:
                f.seek(entry.offset + entry.header_size)
                raw = f.read((entry.size + 15) // 16 * 16 if entry.flags & 1 else entry.size)
                result = (AES.new(self.key, AES.MODE_ECB).decrypt(raw)
                          if entry.flags & 1 else raw)[:entry.size]
        if len(result) != entry.size:
            raise ValueError(f'Decoded size mismatch: {entry.path}')
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('pak', type=Path)
    p.add_argument('--key-file', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prefix', action='append', default=[])
    p.add_argument('--list', action='store_true')
    args = p.parse_args()
    key = bytes.fromhex(args.key_file.read_text().strip()) if args.key_file else None
    pak = Pak(args.pak, key)
    args.output.mkdir(parents=True, exist_ok=True)
    selected = [e for e in pak.entries if not args.prefix or
                any(e.path.startswith(prefix) for prefix in args.prefix)]
    manifest = {'pak': str(args.pak.resolve()), 'version': pak.version,
                'encrypted_index': pak.encrypted_index, 'index_sha1_verified': True,
                'mount': pak.mount, 'total_entries': len(pak.entries),
                'selected_entries': [e.path for e in selected]}
    (args.output / (args.pak.stem + '-manifest.json')).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.list:
        destination = args.output.resolve()
        for e in selected:
            target = (destination / e.path).resolve()
            if destination not in target.parents:
                raise ValueError(f'Unsafe PAK path {e.path}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pak.read(e))
    print(json.dumps({'pak': args.pak.name, 'total': len(pak.entries),
                      'selected': len(selected), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
