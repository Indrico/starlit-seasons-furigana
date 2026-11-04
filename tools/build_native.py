"""Build the bundled native bridge with an installed x64 MSVC toolchain."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(output, msvc=None, sdk=None):
    if msvc is None:
        candidates = sorted(Path('C:/Program Files/Microsoft Visual Studio').glob('*/**/VC/Tools/MSVC/*/bin/HostX64/x64/cl.exe'), reverse=True)
        if not candidates:
            raise RuntimeError('Install the MSVC x64 C++ build tools, or provide --msvc')
        msvc = candidates[0].parents[3]
    msvc = Path(msvc).resolve()
    sdk = Path(sdk or 'C:/Program Files (x86)/Windows Kits/10').resolve()
    versions = sorted((sdk / 'Include').glob('*'), reverse=True)
    version = next((p.name for p in versions if (p / 'um/Windows.h').is_file() and (sdk / 'Lib' / p.name / 'ucrt/x64/ucrt.lib').is_file()), None)
    if not version:
        raise RuntimeError('The Windows SDK x64 headers and libraries are required')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PATH'] = str(msvc / 'bin/HostX64/x64') + os.pathsep + env['PATH']
    env['INCLUDE'] = os.pathsep.join(map(str, [msvc / 'include', *(sdk / 'Include' / version / p for p in ['ucrt', 'shared', 'um'])]))
    env['LIB'] = os.pathsep.join(map(str, [msvc / 'lib/x64', *(sdk / 'Lib' / version / p for p in ['ucrt/x64', 'um/x64'])]))
    vendor = ROOT / 'native/vendor/minhook'
    sources = [ROOT / 'native/bridge.cpp', *(vendor / 'src' / p for p in ['buffer.c', 'hook.c', 'trampoline.c', 'hde/hde64.c'])]
    command = [str(msvc / 'bin/HostX64/x64/cl.exe'), '/nologo', '/O2', '/MT', '/EHsc', '/std:c++17', '/LD', '/I' + str(vendor / 'include'), *map(str, sources), '/link', '/OUT:' + str(output), '/INCREMENTAL:NO', '/Brepro', 'bcrypt.lib']
    subprocess.run(command, cwd=output.parent, env=env, check=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/build/StarlitFuriganaNative.dll')
    parser.add_argument('--msvc', type=Path)
    parser.add_argument('--sdk', type=Path)
    args = parser.parse_args()
    print(build(args.output, args.msvc, args.sdk))
