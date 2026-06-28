"""
ETABS Seismic Optimization Tool - Phase 1
MASTER SCRIPT — Orchestrates everything end to end
===================================================
Run this after verifying all sub-modules work individually.
This is what Phase 2 (optimizer) will call in its inner loop.
"""

import os
import sys
import json
import time

# ─── Project imports ─────────────────────────────────────────────────────────
# All modules are in the same folder; run from project root.
sys.path.insert(0, os.path.dirname(__file__))

from connect_etabs     import get_sap_model, disconnect_etabs
from read_model        import read_all_model_data, sections_to_dataframe, frames_to_dataframe
from modify_sections   import snapshot_section_assignments, define_section_library
from run_analysis      import full_analysis_run
from extract_results   import get_all_story_drifts, get_base_shear, get_modal_results
from evaluate_design   import evaluate_design
from logging_results   import RunLogger


# ─── CONFIGURATION — edit these before running ───────────────────────────────

CONFIG = {
    # ETABS connection
    "edb_path":    r"C:\Projects\MyBuilding\MyBuilding.EDB",  # ← YOUR MODEL PATH
    "launch_new":  False,   # True = launch new ETABS, False = attach to running
    "visible":     True,    # False = hide ETABS window (faster)

    # Load case names in your model (verify with Step 3 output)
    "modal_case":      "Modal",
    "seismic_x_case":  "RS_X",     # Response spectrum X direction
    "seismic_y_case":  "RS_Y",     # Response spectrum Y direction
    "analysis_cases":  ["Modal", "RS_X", "RS_Y"],

    # Materials (must exist in model already)
    "concrete_mat": "4000Psi",      # or "C4000", check ETABS material names
    "rebar_mat":    "Grade60",      # or "A615Gr60"

    # ASCE 7 limits
    "drift_limit":  0.020,          # 2% for Risk Cat II

    # Logging
    "results_dir":  "results",
    "save_every":   5,              # auto-save every N runs
}


# ─── Section library — customize to your column/beam size candidates ──────────

SECTION_LIBRARY = {
    # Beams: B{width}x{depth} — width is short dim, depth is long dim
    "B14x20": {"type": "beam",   "width": 14, "depth": 20},
    "B16x24": {"type": "beam",   "width": 16, "depth": 24},
    "B18x24": {"type": "beam",   "width": 18, "depth": 24},
    "B18x30": {"type": "beam",   "width": 18, "depth": 30},
    "B21x27": {"type": "beam",   "width": 21, "depth": 27},
    "B24x30": {"type": "beam",   "width": 24, "depth": 30},

    # Columns: C{width}x{depth}
    "C18x18": {"type": "column", "width": 18, "depth": 18},
    "C20x20": {"type": "column", "width": 20, "depth": 20},
    "C24x24": {"type": "column", "width": 24, "depth": 24},
    "C28x28": {"type": "column", "width": 28, "depth": 28},
    "C30x30": {"type": "column", "width": 30, "depth": 30},
    "C36x36": {"type": "column", "width": 36, "depth": 36},
}


def phase1_main():
    print("=" * 65)
    print("ETABS Seismic Optimization — Phase 1 Master Run")
    print("=" * 65)

    # ── 1. Connect ──────────────────────────────────────────────────────────
    print("\n[1/7] Connecting to ETABS...")
    etabs_obj, sap_model = get_sap_model(
        edb_path = CONFIG["edb_path"] if os.path.isfile(CONFIG["edb_path"]) else None,
        launch   = CONFIG["launch_new"],
        visible  = CONFIG["visible"],
    )

    # ── 2. Read model data ─────────────────────────────────────────────────
    print("\n[2/7] Reading model data...")
    model_data = read_all_model_data(sap_model)
    frames     = model_data['frames']
    stories    = model_data['stories']
    load_info  = model_data['load_info']

    print(f"\n  Frames: {len(frames)} "
          f"({sum(1 for f in frames if f.obj_type=='Beam')} beams, "
          f"{sum(1 for f in frames if f.obj_type=='Column')} columns)")
    print(f"  Stories: {[s.name for s in stories]}")
    print(f"  Load cases: {load_info['load_cases']}")

    # Save original sections for undo
    snapshot = snapshot_section_assignments(frames)

    # ── 3. Define section library ──────────────────────────────────────────
    print("\n[3/7] Defining section library...")
    created = define_section_library(
        sap_model,
        SECTION_LIBRARY,
        concrete_mat = CONFIG["concrete_mat"],
        rebar_mat    = CONFIG["rebar_mat"],
    )
    print(f"  Defined sections: {created}")

    # ── 4. Verify load cases ───────────────────────────────────────────────
    print("\n[4/7] Verifying load cases...")
    available = set(load_info['load_cases'])
    for lc in CONFIG['analysis_cases']:
        status = "✓" if lc in available else "✗ MISSING"
        print(f"  {status}  {lc}")

    missing = [lc for lc in CONFIG['analysis_cases'] if lc not in available]
    if missing:
        print(f"\n  ✗ Missing load cases: {missing}")
        print("  Update CONFIG['analysis_cases'] to match your model.")
        print("  Available:", sorted(available))
        # Don't exit — let user fix, but show what's available

    # ── 5. Test: single evaluate_design() call ────────────────────────────
    print("\n[5/7] Testing evaluate_design() with example config...")

    # Build a test config using the first story's actual section names
    beam_sections = {f.section_name for f in frames if f.obj_type == "Beam"}
    col_sections  = {f.section_name for f in frames if f.obj_type == "Column"}

    # Use the model's own existing sections for the test
    test_beam_sec = next(iter(beam_sections)) if beam_sections else "B18x24"
    test_col_sec  = next(iter(col_sections))  if col_sections  else "C24x24"

    test_config = {}
    for story in stories:
        test_config[f"{story.name}_Beams"]   = test_beam_sec
        test_config[f"{story.name}_Columns"] = test_col_sec

    print(f"  Test config: {test_config}")

    logger = RunLogger(
        output_dir   = CONFIG['results_dir'],
        project_name = "phase1_test",
        save_every   = CONFIG['save_every'],
    )

    result = evaluate_design(
        sap_model        = sap_model,
        frames           = frames,
        section_snapshot = snapshot,
        design_config    = test_config,
        analysis_cases   = CONFIG['analysis_cases'],
        modal_case       = CONFIG['modal_case'],
        seismic_x_case   = CONFIG['seismic_x_case'],
        seismic_y_case   = CONFIG['seismic_y_case'],
        drift_limit      = CONFIG['drift_limit'],
        run_design       = True,
        concrete_mat     = CONFIG['concrete_mat'],
        rebar_mat        = CONFIG['rebar_mat'],
    )

    run_id = logger.log(result)

    # ── 6. Save and summarize ──────────────────────────────────────────────
    print("\n[6/7] Saving results...")
    save_path = logger.save()
    logger.print_summary()

    # ── 7. Save model snapshot to JSON ────────────────────────────────────
    print("\n[7/7] Saving model snapshot for Phase 2...")
    snapshot_data = {
        "sections": [
            {"name": s.name, "type": s.section_type, "depth": s.depth, "width": s.width}
            for s in model_data['sections']
        ],
        "story_names":    [s.name for s in stories],
        "story_heights":  [s.height for s in stories],
        "beam_sections":  list(beam_sections),
        "col_sections":   list(col_sections),
        "load_cases":     load_info['load_cases'],
        "load_combos":    load_info['load_combos'],
    }
    snapshot_path = os.path.join(CONFIG['results_dir'], "model_snapshot.json")
    os.makedirs(CONFIG['results_dir'], exist_ok=True)
    with open(snapshot_path, 'w') as f:
        json.dump(snapshot_data, f, indent=2)
    print(f"  ✓ Model snapshot saved: {snapshot_path}")

    # ── Disconnect ────────────────────────────────────────────────────────
    disconnect_etabs(etabs_obj, sap_model, save=False)

    print("\n" + "=" * 65)
    print("Phase 1 complete. Review results in:", CONFIG['results_dir'])
    print("=" * 65)

    return result


if __name__ == "__main__":
    phase1_main()
