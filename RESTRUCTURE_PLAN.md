# Plan: one `snap-kits` repo, a folder per model

Status: plan only (2026-11-09). Do nothing until the Halifax session has pushed its new model, and
no other session is writing to the repo.

## Where things stand

- GitHub `aspen8/halifax-snap-kit`. `main` holds only the two original upload commits; all work is
  on branches:
  - `phase1-airframe`: the Halifax (files at the repo root). The Halifax session works here and is
    about to push another model.
  - `hawk-red-arrows`: the Hawk (`hawk/`), branched from an older `phase1-airframe`, so it also
    carries an older copy of the Halifax root files. Newer Halifax commits (e.g. 88e3b12 "Test plate
    round 2") are not in it.
- Shared between the kits: `cad/kitlib.py`, `cad/bambu_x2d_project_settings.json` (the Bambu
  template, including the slower second-nozzle speeds from Hawk v26), `tools/`, `LESSONS.md`,
  `requirements.txt`.
- Not tracked: `ref/`, `out/`, `.venv/` (`.gitignore`).
- `.git` is about 830 MB: every version's STLs, 3MFs and PNGs are committed.

## Target layout

```
README.md            index: one line and a photo per kit, how to build, shared tools
LESSONS.md           shared lessons (both kits' sections kept)
requirements.txt
common/              kitlib.py, bambu_x2d_project_settings.json, tools/
halifax/             cad/ (halifax.py, colour.py, detail.py, render_colour.py, fit tests, ref/),
                     kit/, stl/, docs/, halifax.3mf, README.md, HANDOFF.md
hawk/                as now (cad/, kit/, stl/, docs/, tools/, README.md); HANDOFF.md moves in here
<new model>/         whatever the Halifax session adds, in its own folder
```

## Steps

1. **Wait** for the Halifax session's push. Note its branch and last commit.
2. **Merge into `main`** (a merge branch, then fast-forward `main`):
   - `phase1-airframe` first (newest Halifax), then `hawk-red-arrows`.
   - Expected conflicts in the shared files. Rules: Halifax root files from `phase1-airframe`;
     `hawk/` from `hawk-red-arrows`; `cad/kitlib.py` merged by hand (check both kits' calls still
     work, e.g. `write_3mf` filament maps, `spring_key`); the settings template from
     `hawk-red-arrows` (second-nozzle speeds) unless the Halifax side changed it too; `LESSONS.md`
     both sides' sections.
3. **Move files with `git mv`** on a `restructure` branch (history follows with `git log --follow`):
   - Halifax root files into `halifax/`; shared files into `common/`; root `HANDOFF.md` split into
     `halifax/HANDOFF.md` and `hawk/HANDOFF.md`.
   - The new model into its own folder if it isn't already.
4. **Fix paths**:
   - `hawk/cad/hawk.py`: `parents[2] / "cad"` becomes `parents[2] / "common"`; the same in
     `halifax/cad/*.py`, `hawk/cad/colour.py` (`ROOT`), `hawk/cad/test_coupons.py`, `tools/*.py`
     (`refs.json`, `ROOT`).
   - `kitlib.DEFAULT_TEMPLATE` stays beside kitlib, so it moves with it.
   - Untracked `ref/`: `ref/hawk*` into `hawk/ref/`, the rest into `halifax/ref/`, and the
     `.gitignore` entries to match (paths in `hawk/tools/refs.json` and the READMEs too).
   - Every README and HANDOFF path, including the build commands.
5. **Verify nothing changed**: rebuild each kit from the new layout (Hawk: `hawk.py`, `colour.py`,
   `test_coupons.py`; Halifax: its build) and compare against the pre-move outputs (part volumes,
   STL bounding boxes, plate lists); run the interference check; slice one plate per kit in Bambu
   Studio.
6. **Rename on GitHub**: `gh repo rename snap-kits` (old URLs redirect). Update the remote in every
   local checkout, including the Halifax session's.
7. **Branches**: once merged, delete `phase1-airframe` and `hawk-red-arrows` (with the user's OK);
   new work goes on short branches off `main`.
8. **Kit files from now on**: publish each version's 3MF and STLs as a GitHub Release
   (`gh release create hawk-vNN ...`), and keep only the current 3MF per kit in the repo (or none).
   Shrinking the existing 830 MB history needs a history rewrite and everyone re-cloning: not
   recommended unless the size becomes a problem.

## Needs the user's decision

- Release assets instead of committed STLs/3MFs (step 8).
- Deleting the old branches (step 7).
- Whether the new model gets its own folder now or after it is finished.
