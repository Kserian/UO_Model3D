"""Extract one animation (body / equipment id) from anim.idx + anim.mul into a .vd file (UOFiddler VD layout)."""
import struct, sys, os

def base_index(body):
    if body < 200:
        return body * 110, 22, 0          # high detail monster (22 actions), vd type 0
    if body < 400:
        return 22000 + (body - 200) * 65, 13, 1   # low detail / animal (13 actions), vd type 1
    return 35000 + (body - 400) * 175, 35, 2      # people and equipment (35 actions), vd type 2

def extract(idx_path, mul_path, body, out):
    idx = open(idx_path, "rb").read()
    base, n_act, vtype = base_index(body)
    entries = [struct.unpack_from("<iii", idx, 12 * (base + i)) for i in range(n_act * 5)]
    with open(mul_path, "rb") as f:
        blobs = []
        for look, length, extra in entries:
            if look < 0 or length <= 0:
                blobs.append(None); continue
            f.seek(look); blobs.append(f.read(length))
    head = struct.pack("<hh", 6, vtype)
    pos = 4 + 12 * len(entries)
    table, data = b"", b""
    for b in blobs:
        if b is None:
            table += struct.pack("<iii", -1, -1, -1)
        else:
            table += struct.pack("<iii", pos + len(data), len(b), 0); data += b
    open(out, "wb").write(head + table + data)
    return sum(b is not None for b in blobs)

if __name__ == "__main__":
    idx, mul, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    for body in [int(x, 0) for x in sys.argv[4:]]:
        n = extract(idx, mul, body, os.path.join(out_dir, "anim_%04d.vd" % body))
        print("anim %d: %d blocks" % (body, n))
