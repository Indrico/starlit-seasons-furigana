"""Recover and validate the resource key from the normally running owned game.

Reads only the main module's .text section. Does not inject, alter the process,
patch the executable, launch the game, or alter Steam activation.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import re
import struct

from Crypto.Cipher import AES

from asset_extract import Pak


class ModuleEntry(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('th32ModuleID', W.DWORD),
                ('th32ProcessID', W.DWORD), ('GlblcntUsage', W.DWORD),
                ('ProccntUsage', W.DWORD), ('modBaseAddr', C.POINTER(C.c_byte)),
                ('modBaseSize', W.DWORD), ('hModule', W.HMODULE),
                ('szModule', W.WCHAR * 256), ('szExePath', W.WCHAR * 260)]


def read_text(pid, expected_exe):
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = W.HANDLE
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p,
                                        C.c_size_t, C.POINTER(C.c_size_t)]
    kernel.Module32FirstW.argtypes = [W.HANDLE, C.POINTER(ModuleEntry)]
    kernel.Module32NextW.argtypes = kernel.Module32FirstW.argtypes
    kernel.CloseHandle.argtypes = [W.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x18, pid)
    if snapshot == W.HANDLE(-1).value:
        raise C.WinError(C.get_last_error())
    entry = ModuleEntry()
    entry.dwSize = C.sizeof(entry)
    try:
        valid = kernel.Module32FirstW(snapshot, C.byref(entry))
        while valid and entry.szModule != 'StarlitSeason-Win64-Shipping.exe':
            valid = kernel.Module32NextW(snapshot, C.byref(entry))
        if not valid:
            raise ValueError('PID does not contain the expected Shipping module')
        base = C.cast(entry.modBaseAddr, C.c_void_p).value
        path = Path(entry.szExePath)
        if path.resolve() != expected_exe:
            raise ValueError('PID main-module path does not match the explicitly selected game root')
    finally:
        kernel.CloseHandle(snapshot)
    process = kernel.OpenProcess(0x410, False, pid)  # query information + VM_READ
    if not process:
        raise C.WinError(C.get_last_error())

    def read(address, size):
        buffer = (C.c_char * size)()
        count = C.c_size_t()
        if not kernel.ReadProcessMemory(process, address, buffer, size, C.byref(count)):
            raise C.WinError(C.get_last_error())
        if count.value != size:
            raise ValueError('Partial module read')
        return bytes(buffer)

    try:
        header = read(base, 4096)
        pe, = struct.unpack_from('<I', header, 60)
        if header[pe:pe + 4] != b'PE\0\0':
            raise ValueError('Invalid PE header')
        section_count, = struct.unpack_from('<H', header, pe + 6)
        optional_size, = struct.unpack_from('<H', header, pe + 20)
        for i in range(section_count):
            name, size, rva = struct.unpack_from('<8sII', header, pe + 24 + optional_size + 40 * i)
            if name.rstrip(b'\0') == b'.text':
                return read(base + rva, size), rva, path
        raise ValueError('Main module has no .text section')
    finally:
        kernel.CloseHandle(process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--pak', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expected_exe = (args.game / 'StarlitSeason/Binaries/Win64/StarlitSeason-Win64-Shipping.exe').resolve()
    text, text_rva, exe_path = read_text(args.pid, expected_exe)
    with args.pak.open('rb') as f:
        f.seek(-4096, 2)
        tail = f.read()
        footer = tail.rfind(bytes.fromhex('e1126f5a'))
        offset, = struct.unpack_from('<q', tail, footer + 8)
        f.seek(offset)
        encrypted_head = f.read(16)
    # Compiler forms of eight immediate DWORD stores, including interrupted and
    # descending stores. Each is merely a candidate until index SHA1 validates.
    patterns = [
        (rb'\xc7......\xc7......\xc7......\xc7..........\xc7......\xc7......\xc7......\xc7......',
         [3, 10, 17, 24, 35, 42, 49, 56]),
        (rb'\xc7.....\xc7......\xc7......\xc7......\xc7......\xc7......\xc7......\xc7......',
         [2, 9, 16, 23, 30, 37, 44, 51]),
        (rb'\xc7......\xc7......\x48...\xc7......\xc7......\xc7......\xc7......\xc7......\xc7......',
         [3, 10, 21, 28, 35, 42, 49, 56]),
        (rb'\xc7......\xc7......\xc7......\xc7......\xc7......\xc7......\xc7......\xc7.....\xc3',
         [51, 45, 38, 31, 24, 17, 10, 3]),
    ]
    for pattern, offsets in patterns:
        for match in re.finditer(pattern, text, re.S):
            key = b''.join(text[match.start() + o:match.start() + o + 4] for o in offsets)
            if AES.new(key, AES.MODE_ECB).decrypt(encrypted_head)[4:13] != b'../../../':
                continue
            pak = Pak(args.pak, key)
            args.output.mkdir(parents=True, exist_ok=True)
            key_file = args.output / 'pak-key.hex'
            if key_file.exists() and key_file.read_text().strip() != key.hex():
                raise ValueError('Refusing to replace a different previously recovered key')
            key_file.write_text(key.hex(), encoding='ascii')
            report = {'pid': args.pid, 'exe': str(exe_path),
                      'exe_sha256': hashlib.sha256(exe_path.read_bytes()).hexdigest(),
                      'candidate_rva': hex(text_rva + match.start()),
                      'pak': str(args.pak.resolve()), 'index_sha1': pak.index_sha1,
                      'index_sha1_verified': True, 'entries': len(pak.entries),
                      'method': 'read-only .text of normally launched game'}
            (args.output / 'pak-key-provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
            return
    raise SystemExit('No validated resource key found; game may not have completed startup')


if __name__ == '__main__':
    main()
