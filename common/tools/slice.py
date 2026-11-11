"""
Slice every plate of a Bambu 3MF from the command line and summarise it.

  python common/tools/slice.py kit/halifax_kit.3mf [more.3mf ...] [--out out/slice] [--md]

For each 3MF it runs Bambu Studio once per plate (`--slice N`) into
OUT/<name>/plate_N/, which gets plate_N.gcode, Bambu's result.json and slice.log.
(With `--slice 0`, Bambu stops at the first plate that fails, so the later plates
get no numbers; `--no-check` doesn't change that.) It then prints, per
plate: time, layers, grams on the model, grams wasted on flushing and the prime
tower, filament changes, and every warning or error from the slicer. --md prints
the table as Markdown (for docs/slicing.md).

Exit code 1 if any plate failed to slice or Bambu reported an error other than
the known-harmless ones below. A summary.json goes next to the plate folders.

Notes (see LESSONS.md, "Slicing from the command line"):
- The settings come from the 3MF itself. Bambu warns that it "can not find
  system preset file .../machine_full/..." because the X2D presets ship under
  machine/ and process/; it then uses the full settings embedded in the 3MF.
- "Invalid T command (T65279/T65535)" comes from Bambu's own X2D end G-code
  (unloading both nozzles to the AMS), not from the model.
- --export-3mf fails on macOS ("Unable to open the file ...tmp"), so we don't
  use it. result.json has everything the summary needs.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BAMBU = Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio")
HARMLESS = (
    "Invalid T command (T65279)",
    "Invalid T command (T65535)",
    "can not find system preset file",
    "no filament colors found in projects",
    "building nozzle list from filament map",
    "Current BambuStudio Version",
)
ROOT = Path(__file__).resolve().parents[2]          # repo root (this is common/tools/)


def filament_names():
    """Slot -> name from cad/colour.py FILAMENTS, without importing CadQuery."""
    src = (ROOT / "halifax" / "cad" / "colour.py").read_text()
    return {int(s): n for s, n in re.findall(r'^\s+(\d+): \("([^"]+)"', src, re.M)}


def gcode_header(path):
    info = {}
    with open(path, errors="replace") as f:
        for i, line in enumerate(f):
            if i > 400:
                break
            if m := re.match(r"; total layer number: (\d+)", line):
                info["layers"] = int(m[1])
            elif m := re.match(r"; max_z_height: ([\d.]+)", line):
                info["height"] = float(m[1])
            elif m := re.match(r"; model printing time: .*; total estimated time: (.+)", line):
                info["time_str"] = m[1].strip()
    return info


def layer_heights(path):
    """Distinct layer heights after the first layer, ignoring bridges (Bambu
    prints thick bridges and labels them 0.4)."""
    hs, layer, feature = set(), 0, ""
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("; CHANGE_LAYER"):
                layer += 1
            elif line.startswith("; FEATURE:"):
                feature = line[10:].strip()
            elif line.startswith("; LAYER_HEIGHT:") and layer > 1 and feature != "Bridge":
                hs.add(round(float(line.split(":")[1]), 2))
    return sorted(hs)


def hm(seconds):
    m = round(seconds / 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


def run_bambu(src, plate, workdir):
    """Slice one plate into workdir. Returns (exit code, result.json dict, errors, warnings)."""
    workdir.mkdir(parents=True)
    log = workdir / "slice.log"
    with open(log, "w") as f:
        p = subprocess.run([str(BAMBU), "--debug", "2", "--slice", str(plate), "--outputdir", str(workdir),
                            str(src)], stdout=f, stderr=subprocess.STDOUT, cwd=workdir)
    rj = workdir / "result.json"
    result = json.loads(rj.read_text()) if rj.exists() else {}
    errors, warnings = [], []
    for line in log.read_text(errors="replace").splitlines():
        m = re.search(r"\[(warning|error)\]\s+(.*)", line)
        if m and not any(h in line for h in HARMLESS):
            (errors if m[1] == "error" else warnings).append(m[2].strip())
    if p.returncode != 0 and not errors:
        errors.append(f"Bambu exit {p.returncode}: {result.get('error_string', 'no result.json')}")
    return p.returncode, result, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def slice_one(src, out_root, names):
    """Slice each plate on its own (--slice N): with --slice 0 Bambu stops at the
    first plate with a path conflict and the later plates get no numbers."""
    out = out_root / src.stem
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    with zipfile.ZipFile(src) as z:
        cfg = json.loads(z.read("Metadata/project_settings.config"))
        n_plates = z.read("Metadata/model_settings.config").decode().count("<plate>")
    plates = []
    for i in range(1, n_plates + 1):
        work = out / f"plate_{i}"
        code, result, errors, warnings = run_bambu(src, i, work)
        sliced = {sp["id"]: sp for sp in result.get("sliced_plates", [])}
        sp = sliced.get(i)
        g = work / f"plate_{i}.gcode"
        ok = code == 0 and sp is not None and g.exists()
        row = {"plate": i, "ok": ok, "errors": errors, "warnings": warnings}
        if sp is not None and g.exists():
            head = gcode_header(g)
            fil = sp.get("filaments", [])
            model = sum(x["main_used_g"] for x in fil)
            total = sum(x["total_used_g"] for x in fil)
            row.update({
                "seconds": sp.get("total_predication", 0),
                "time": hm(sp.get("total_predication", 0)),
                "layers": head.get("layers"),
                "height": head.get("height"),
                "layer_heights": layer_heights(g),
                "filaments": [(names.get(x["id"], f"slot {x['id']}"), round(x["main_used_g"], 1),
                               round(x["total_used_g"], 1)) for x in fil],
                "model_g": round(model, 1),
                "waste_g": round(total - model, 1),
                "changes": sp.get("filament_change_times", 0),
                "objects": [o["name"] for o in sp.get("objects", [])],
            })
        plates.append(row)
    return {"file": str(src), "printer": cfg.get("printer_settings_id"),
            "process": cfg.get("print_settings_id"), "plates": plates}


def print_md(r):
    print(f"### {Path(r['file']).name}\n")
    print(f"Printer `{r['printer']}`, process `{r['process']}`.\n")
    print("| Plate | Time | Layers | Layer mm | Filament on the model (g) | Model g | Flush + tower g | Changes |")
    print("|---|---|---|---|---|---|---|---|")
    done = [p for p in r["plates"] if "seconds" in p]
    for p in r["plates"]:
        if "seconds" not in p:
            print(f"| {p['plate']} | **failed** | | | | | | |")
            continue
        fil = ", ".join(f"{n} {g}" for n, g, _ in p["filaments"])
        hs = "/".join(f"{h:g}" for h in p["layer_heights"])
        print(f"| {p['plate']} | {p['time']} | {p['layers']} | {hs} | {fil} | {p['model_g']} "
              f"| {p['waste_g']} | {p['changes']} |")
    print(f"| **All sliced** | **{hm(sum(p['seconds'] for p in done))}** | | | "
          f"| **{round(sum(p['model_g'] for p in done), 1)}** "
          f"| **{round(sum(p['waste_g'] for p in done), 1)}** "
          f"| **{sum(p['changes'] for p in done)}** |\n")
    msgs = [(p["plate"], k, m) for p in r["plates"] for k in ("errors", "warnings") for m in p[k]]
    if msgs:
        print("Slicer messages:\n")
        for pl, k, m in msgs:
            m = re.sub(r"^plate \d+: (found NON_CRITICAL slicing warnings: )?", "", m)
            print(f"- plate {pl} {k[:-1]}: {m}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "slice")
    ap.add_argument("--md", action="store_true", help="print Markdown tables")
    a = ap.parse_args()
    if not BAMBU.exists():
        sys.exit(f"Bambu Studio not found at {BAMBU}")
    names = filament_names()
    bad = False
    for f in a.files:
        r = slice_one(f.resolve(), a.out.resolve(), names)
        (a.out / f.stem / "summary.json").write_text(json.dumps(r, indent=1))
        if a.md:
            print_md(r)
        else:
            print(f"== {f}  ({r['printer']}; {r['process']})")
            for p in r["plates"]:
                if "seconds" in p:
                    fil = ", ".join(f"{n} {g}g" for n, g, _ in p["filaments"])
                    print(f"  plate {p['plate']:>2}: {p['time']:>7}  {p['layers']} layers  "
                          f"heights {p['layer_heights']}  model {p['model_g']} g  waste {p['waste_g']} g  "
                          f"changes {p['changes']}  [{fil}]")
                else:
                    print(f"  plate {p['plate']:>2}: FAILED")
                for e in p["errors"]:
                    print("      ERROR:", e)
                for w in p["warnings"]:
                    print("      warning:", w)
        bad |= any(not p["ok"] for p in r["plates"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
