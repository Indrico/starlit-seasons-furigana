import struct
import unittest

from texture_geometry import ink_bounds


class TextureGeometryTests(unittest.TestCase):
    def texture(self, pixels, size=None):
        fmt = b'PF_B8G8R8A8\0'
        return b'\0'*16 + struct.pack('<4i', 2, 2, 1, len(fmt)) + fmt + b'\0'*12 + \
            struct.pack('<IIIQ', 0x48, len(pixels), size if size is not None else len(pixels), 0) + pixels

    def test_bgra_alpha_bounds_ignore_transparent_padding(self):
        pixels = bytes((0,0,0,0, 10,20,30,255, 0,0,0,0, 10,20,30,255))
        self.assertEqual(ink_bounds(self.texture(pixels)), {'left': 0.5, 'right': 1.0, 'top': 0.0})

    def test_empty_or_unknown_texture_does_not_add_an_overlay(self):
        self.assertIsNone(ink_bounds(b'not a texture'))
        self.assertIsNone(ink_bounds(self.texture(b'\0'*16)))

    def test_malformed_mip_is_rejected(self):
        with self.assertRaises(ValueError):
            ink_bounds(self.texture(b'\0'*16, size=12))
