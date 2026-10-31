"""Measure outline profiles from silhouette masks (diagnostic)."""
import sys
import numpy as np
from PIL import Image
m = np.asarray(Image.open(sys.argv[1])) > 127
H, W = m.shape
cols = np.nonzero(m.any(0))[0]
rows = np.nonzero(m.any(1))[0]
print("cols", cols.min(), cols.max(), "rows", rows.min(), rows.max())
mode = sys.argv[2]
if mode == "plan":
    # centreline: row of the nose probe at the rightmost columns
    xr = cols.max()
    probe_rows = np.nonzero(m[:, xr - 5])[0]
    cl = probe_rows.mean()
    print("centreline row", cl)
    for x in range(cols.max(), cols.min(), -int(sys.argv[3]) if len(sys.argv) > 3 else -20):
        col = m[:, x]
        r = int(round(cl))
        if not col[r]:
            print(x, "gap"); continue
        a = r
        while a > 0 and col[a - 1]: a -= 1
        b = r
        while b < H - 1 and col[b + 1]: b += 1
        print(x, a, b, f"half {(b - a) / 2:.0f}  up {cl - a:.0f} dn {b - cl:.0f}")
else:
    for x in range(cols.min(), cols.max(), int(sys.argv[3]) if len(sys.argv) > 3 else 20):
        r = np.nonzero(m[:, x])[0]
        if len(r): print(x, r.min(), r.max())
