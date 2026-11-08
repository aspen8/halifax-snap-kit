"""
Copy a Bambu 3MF with every plate set to print every filament from the main (left) nozzle, so
the AMS swaps colours in one nozzle instead of handing them to the second one. For comparing
print quality and time against the two-nozzle file.

  python tools/single_nozzle.py IN.3mf OUT.3mf
"""
import json
import re
import sys
import zipfile


def main(src, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "Metadata/model_settings.config":
                txt = data.decode()
                txt = re.sub(r'(key="filament_maps" value=")([0-9 ]+)(")',
                             lambda m: m.group(1) + " ".join("1" for _ in m.group(2).split()) + m.group(3), txt)
                txt = txt.replace('key="filament_map_mode" value="Auto For Flush"', 'key="filament_map_mode" value="Manual"')
                data = txt.encode()
            elif item.filename == "Metadata/project_settings.config":
                d = json.loads(data.decode())
                if "filament_map" in d:
                    d["filament_map"] = ["1"] * len(d["filament_map"])
                    d["filament_map_mode"] = "Manual"
                data = json.dumps(d, indent=4).encode()
            zout.writestr(item, data)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
