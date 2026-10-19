"""Reader for the UO animation frame archives `AnimationFrame1..4.uop` (client 7.x; they hold the animations that are not in anim*.mul, e.g. gargoyle and the
Stygian Abyss equipment) and a converter of one (body, action) entry into the block layout of anim*.mul.

Entry `build/animationlegacyframe/<body:06d>/<action:02d>.bin` (the file name is found by the Jenkins lookup3 hash, no names are stored): header "AMOU", version,
length, body, ..., palette (256 x BGRA, not used), number of frames F (5 directions x F/5 frames, direction-major), offset of the frame table; frame table = F x 16 bytes
(id, bbox, offset); each frame = 512 bytes 16-bit palette + (centerX, centerY, width, height) + the same RLE runs as in anim.mul.
"""
import struct, zlib

M = 0xFFFFFFFF


def _rot(x, k):
    return ((x << k) | (x >> (32 - k))) & M


def _mix(a, b, c):
    a = (a - c) & M; a ^= _rot(c, 4); c = (c + b) & M
    b = (b - a) & M; b ^= _rot(a, 6); a = (a + c) & M
    c = (c - b) & M; c ^= _rot(b, 8); b = (b + a) & M
    a = (a - c) & M; a ^= _rot(c, 16); c = (c + b) & M
    b = (b - a) & M; b ^= _rot(a, 19); a = (a + c) & M
    c = (c - b) & M; c ^= _rot(b, 4); b = (b + a) & M
    return a, b, c


def uop_hash(name):
    """64 bit hash of a file name in a .uop table (lookup3 hashlittle2, both seeds 0)"""
    k = name.encode()
    n = len(k)
    a = b = c = (0xDEADBEEF + n) & M
    i = 0
    while n - i > 12:
        a = (a + int.from_bytes(k[i:i + 4], "little")) & M
        b = (b + int.from_bytes(k[i + 4:i + 8], "little")) & M
        c = (c + int.from_bytes(k[i + 8:i + 12], "little")) & M
        a, b, c = _mix(a, b, c)
        i += 12
    if n - i == 0:
        return (b << 32) | c
    r = k[i:] + b"\0" * 12
    a = (a + int.from_bytes(r[0:4], "little")) & M
    b = (b + int.from_bytes(r[4:8], "little")) & M
    c = (c + int.from_bytes(r[8:12], "little")) & M
    c ^= b; c = (c - _rot(b, 14)) & M
    a ^= c; a = (a - _rot(c, 11)) & M
    b ^= a; b = (b - _rot(a, 25)) & M
    c ^= b; c = (c - _rot(b, 16)) & M
    a ^= c; a = (a - _rot(c, 4)) & M
    b ^= a; b = (b - _rot(a, 14)) & M
    c ^= b; c = (c - _rot(b, 24)) & M
    return (b << 32) | c


def read_table(f):
    """{hash: (offset, header length, compressed length, decompressed length, compression flag)} of an open .uop file"""
    magic, _, _, nxt, _, _ = struct.unpack("<4sIIQII", f.read(28))
    assert magic == b"MYP\0", magic
    ents = {}
    while nxt:
        f.seek(nxt)
        n, nxt = struct.unpack("<IQ", f.read(12))
        for _ in range(n):
            off, hl, cl, dl, h, _, fl = struct.unpack("<QIIIQIH", f.read(34))
            if off:
                ents[h] = (off, hl, cl, dl, fl)
    return ents


def frame_name(body, action):
    return "build/animationlegacyframe/%06d/%02d.bin" % (body, action)


class Frames:
    """(body, action) -> entry of AnimationFrame1..4.uop; `bodies` = the ids to look for (actions 0..max_action)"""

    def __init__(self, client_dir, bodies, max_action=99):
        import os
        self.files, self.index = {}, {}
        tables = {}
        for n in (1, 2, 3, 4):
            p = os.path.join(client_dir, "AnimationFrame%d.uop" % n)
            if os.path.exists(p):
                self.files[n] = open(p, "rb")
                tables[n] = read_table(self.files[n])
        for b in bodies:
            for a in range(max_action + 1):
                h = uop_hash(frame_name(b, a))
                for n, t in tables.items():
                    if h in t:
                        self.index[(b, a)] = (n, t[h])
                        break
        self.cache = {}

    def actions(self, body):
        return sorted(a for (b, a) in self.index if b == body)

    def blocks(self, body, action):
        """list of 5 blocks (numpy uint8 array in the anim.mul block layout) for the directions, [] when the entry is missing or has no 5 x F frames"""
        key = (body, action)
        if key not in self.cache:
            if len(self.cache) > 32:
                self.cache.clear()
            self.cache[key] = self._load(key)
        return self.cache[key]

    def _load(self, key):
        import numpy as np
        if key not in self.index:
            return []
        n, (off, hl, cl, dl, fl) = self.index[key]
        f = self.files[n]
        f.seek(off + hl)
        raw = f.read(cl)
        d = zlib.decompress(raw) if fl == 1 else raw
        if d[:4] != b"AMOU":
            return []
        nf, tab = struct.unpack_from("<II", d, 32)[0], struct.unpack_from("<I", d, 36)[0]
        if nf % 5 or nf == 0:
            return []
        starts = [tab + 16 * i + struct.unpack_from("<I", d, tab + 16 * i + 12)[0] + 512 for i in range(nf)]
        bounds = sorted(starts) + [len(d)]
        end = {s: bounds[i + 1] for i, s in enumerate(bounds[:-1])}
        per, out = nf // 5, []
        for dr in range(5):
            fr = [d[s:end[s]] for s in starts[dr * per:(dr + 1) * per]]
            offs, o = [], 4 + 4 * per
            for x in fr:
                offs.append(o)
                o += len(x)
            blk = b"\0" * 512 + struct.pack("<i", per) + struct.pack("<%di" % per, *offs) + b"".join(fr)
            out.append(np.frombuffer(blk, np.uint8))
        return out
