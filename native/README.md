# Native dialogue bridge

The bridge targets the original Shipping executable for Steam build 8278842.
It validates the disk executable SHA-256 and live function prefixes before
installing in-memory hooks. Original executables and game archives are intact.

The message command handlers provide complete native text before the first
visible frame. The native reveal function completes that text without invoking
skip/stop-voice handlers. The message-wait hook controls progression separately
from character animation and sound. The native advance path lets Lua consume
intermediate pages, and the cleanup path restores renderer state.

Communication uses the pinned UE4SS DLL's `execute_lua_in_mod` and
`call_script_function` C exports. Calls run on the game thread. The DLL is
loaded as a Lua C module, with no direct dependency on a Lua DLL or the C++ SDK
ABI for the dialogue callbacks. A Lua callback failure releases the current progression gate.

UI geometry additionally uses the pinned loader's exported LuaMadeSimple scalar
accessors and UObject::ProcessEvent. The opaque FGeometry return cannot be
marshalled field-by-field by this loader. `sf_geometry` instead copies the native
return and exposes 13 finite scalar values (size, accumulated layout/render
transforms, and origins) on the game thread. `ui_geometry.lua` converts desktop
positions to parent-local coordinates and rejects singular, rotated, or sheared
transforms. This small ABI adapter is specific to the pinned loader and UE4.24;
do not upgrade either without rechecking its constructor/storage and struct size.

`sf_clock` exposes QueryPerformanceCounter seconds for cooperative UI scheduling.
These entry points do not modify game archives or add native function hooks.

`vendor/minhook` contains the x64 sources from MinHook v1.3.4, commit
`c3fcafdc10146beb5919319d0683e44e3c30d537`, with its original license.
Build with `python tools/build_native.py` using installed MSVC x64 tools and the
Windows SDK. Players receive the precompiled DLL in the portable package.

Function RVAs for this exact build:

| RVA | Purpose |
| --- | --- |
| `0xd4f1d0` | CML message assignment |
| `0xd50a70` | Script-text message assignment |
| `0xd51a00` | Native text reveal |
| `0xd52920` | Message completion wait |
| `0xd45590` | Native advance input |
| `0xd4da70` | Message component cleanup |
| `0xd62970` | Answer-choice setup |

The initial local probe confirmed manual waiting, one Enter advancing a line,
and automatic progression resuming in Album. Broader verification is recorded
in the runtime documentation after implementation testing.
