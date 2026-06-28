"""
ETABS Seismic Optimization Tool - Phase 1
Step 7: The "Evaluate One Design" Function
==========================================
This is the core function the optimizer will call thousands of times.
It applies a section configuration, runs analysis, extracts results,
checks ASCE 7 compliance, and returns a results dictionary.
"""

import time
import traceback
from typing import Dict, List, Optional

# ASCE 7-22 Table 12.12-1 drift limits (story drift ratio)
# Risk Category II, most buildings
DRIFT_LIMIT_ASCE7 = {
    "default":          0.020,   # 2.0% — most structures
    "masonry":          0.010,   # 1.0%
    "other_structures": 0.015,   # 1.5%
}


def evaluate_design(
    sap_model,
    frames: list,
    section_snapshot: Dict[str, str],
    design_config: Dict[str, str],      # {group_or_key: section_name}
    analysis_cases: List[str],          # e.g. ["RS_X", "RS_Y", "Modal"]
    modal_case: str = "Modal",
    seismic_x_case: str = "RS_X",
    seismic_y_case: str = "RS_Y",
    drift_limit: float = 0.020,
    run_design: bool = True,
    concrete_mat: str = "4000Psi",
    rebar_mat: str = "Grade60",
) -> Dict:
    """
    Complete evaluation of ONE design configuration.

    Parameters
    ----------
    sap_model       : ETABS SapModel COM object
    frames          : list of FrameObject (from read_frame_objects)
    section_snapshot: original section dict {unique_name: section} for undo
    design_config   : {group_name: section_name} to apply
    analysis_cases  : list of load case names to run
    drift_limit     : ASCE 7 drift ratio limit (default 0.02)
    run_design      : if True, also runs concrete frame design for DCR

    Returns
    -------
    dict with keys:
      - design_config      : input (echoed back)
      - analysis_ok        : bool
      - max_drift_X        : max story drift ratio in X direction
      - max_drift_Y        : max story drift ratio in Y direction
      - story_drifts_X     : {story: drift} dict
      - story_drifts_Y     : {story: drift} dict
      - Vx_kip             : base shear in X
      - Vy_kip             : base shear in Y
      - T1_sec             : fundamental period
      - T2_sec             : second period
      - SumUX_pct          : cumulative mass participation X
      - SumUY_pct          : cumulative mass participation Y
      - max_col_pmm_dcr    : max column PMM demand/capacity ratio
      - n_beam_fail        : number of beams that failed design
      - n_col_fail         : number of columns that failed design
      - drift_pass_X       : bool (True if max_drift_X ≤ limit)
      - drift_pass_Y       : bool (True if max_drift_Y ≤ limit)
      - overall_pass       : bool (passes drift AND design)
      - run_time_sec       : wall time for this evaluation
      - error_msg          : "" if OK, else error description
    """
    t_start = time.time()

    # ── Default result ───────────────────────────────────────────────────────
    result = {
        'design_config':     design_config,
        'analysis_ok':       False,
        'max_drift_X':       999.0,
        'max_drift_Y':       999.0,
        'story_drifts_X':    {},
        'story_drifts_Y':    {},
        'Vx_kip':            0.0,
        'Vy_kip':            0.0,
        'T1_sec':            0.0,
        'T2_sec':            0.0,
        'SumUX_pct':         0.0,
        'SumUY_pct':         0.0,
        'max_col_pmm_dcr':   999.0,
        'n_beam_fail':       999,
        'n_col_fail':        999,
        'drift_pass_X':      False,
        'drift_pass_Y':      False,
        'overall_pass':      False,
        'run_time_sec':      0.0,
        'error_msg':         '',
    }

    try:
        # ── STEP 1: Unlock and apply sections ────────────────────────────────
        from connect_etabs import unlock_model
        from modify_sections import apply_design_config, define_section_library
        from run_analysis import full_analysis_run
        from extract_results import (
            get_all_story_drifts, get_base_shear,
            get_modal_results, get_max_dcr_all_frames
        )

        unlock_model(sap_model)

        # First ensure all referenced sections exist
        # (sections should already be defined in model, but define if new)
        ok = apply_design_config(sap_model, frames, design_config,
                                  concrete_mat, rebar_mat)
        if not ok:
            result['error_msg'] = "Section assignment failed."
            return _finalize(result, t_start)

        # ── STEP 2: Run analysis ──────────────────────────────────────────────
        analysis_ok = full_analysis_run(sap_model, analysis_cases,
                                         run_design=run_design)
        result['analysis_ok'] = analysis_ok

        if not analysis_ok:
            result['error_msg'] = "Analysis failed. Check ETABS log."
            # Restore sections before returning
            from modify_sections import restore_section_assignments
            restore_section_assignments(sap_model, section_snapshot)
            return _finalize(result, t_start)

        # ── STEP 3: Extract story drifts ──────────────────────────────────────
        drifts_X = get_all_story_drifts(sap_model, seismic_x_case).get('X', {})
        drifts_Y = get_all_story_drifts(sap_model, seismic_y_case).get('Y', {})

        max_drift_X = max(drifts_X.values()) if drifts_X else 0.0
        max_drift_Y = max(drifts_Y.values()) if drifts_Y else 0.0

        result['story_drifts_X'] = drifts_X
        result['story_drifts_Y'] = drifts_Y
        result['max_drift_X']    = max_drift_X
        result['max_drift_Y']    = max_drift_Y

        # ── STEP 4: Base shear ────────────────────────────────────────────────
        shear_X = get_base_shear(sap_model, seismic_x_case)
        shear_Y = get_base_shear(sap_model, seismic_y_case)
        result['Vx_kip'] = shear_X.get('Vx', 0.0)
        result['Vy_kip'] = shear_Y.get('Vy', 0.0)

        # ── STEP 5: Modal results ─────────────────────────────────────────────
        modal = get_modal_results(sap_model, modal_case)
        result['T1_sec']    = modal.get('T1', 0.0)
        result['T2_sec']    = modal.get('T2', 0.0)
        result['SumUX_pct'] = modal.get('SumUX', 0.0) * 100
        result['SumUY_pct'] = modal.get('SumUY', 0.0) * 100

        # ── STEP 6: DCR extraction ────────────────────────────────────────────
        if run_design:
            dcr_data = get_max_dcr_all_frames(sap_model, frames)
            result['max_col_pmm_dcr']  = dcr_data['max_col_pmm_dcr']
            result['n_beam_fail']       = dcr_data['n_beam_design_fail']
            result['n_col_fail']        = dcr_data['n_col_design_fail']
        else:
            result['max_col_pmm_dcr'] = 0.0
            result['n_beam_fail']      = 0
            result['n_col_fail']       = 0

        # ── STEP 7: ASCE 7 compliance checks ─────────────────────────────────
        drift_pass_X = max_drift_X <= drift_limit
        drift_pass_Y = max_drift_Y <= drift_limit
        design_pass  = (result['n_beam_fail'] == 0 and
                        result['n_col_fail']  == 0 and
                        result['max_col_pmm_dcr'] <= 1.0)

        result['drift_pass_X']  = drift_pass_X
        result['drift_pass_Y']  = drift_pass_Y
        result['overall_pass']  = drift_pass_X and drift_pass_Y and design_pass

        _print_summary(result, drift_limit)

    except Exception as e:
        result['error_msg']  = f"Exception: {str(e)}"
        result['overall_pass'] = False
        print(f"  ✗ evaluate_design EXCEPTION:\n{traceback.format_exc()}")

        # Always restore on failure
        try:
            from connect_etabs import unlock_model
            from modify_sections import restore_section_assignments
            unlock_model(sap_model)
            restore_section_assignments(sap_model, section_snapshot)
        except Exception:
            pass

    return _finalize(result, t_start)


def _finalize(result: dict, t_start: float) -> dict:
    result['run_time_sec'] = round(time.time() - t_start, 2)
    return result


def _print_summary(r: dict, limit: float) -> None:
    status = "✓ PASS" if r['overall_pass'] else "✗ FAIL"
    print(
        f"  {status} | "
        f"drift X={r['max_drift_X']:.3f} Y={r['max_drift_Y']:.3f} "
        f"(lim {limit:.3f}) | "
        f"T1={r['T1_sec']:.2f}s | "
        f"Vx={r['Vx_kip']:.0f}k | "
        f"col_PMM={r['max_col_pmm_dcr']:.2f} | "
        f"t={r['run_time_sec']:.1f}s"
    )


# ─── Batch helper: evaluate multiple configs ──────────────────────────────────

def evaluate_batch(
    sap_model,
    frames: list,
    section_snapshot: Dict[str, str],
    configs: List[Dict[str, str]],
    **kwargs
) -> List[Dict]:
    """
    Run evaluate_design() for a list of configurations.
    Each config is a design_config dict.
    Returns list of result dicts.
    """
    results = []
    for i, config in enumerate(configs):
        print(f"\n─── Evaluating config {i+1}/{len(configs)} ───")
        r = evaluate_design(sap_model, frames, section_snapshot, config, **kwargs)
        results.append(r)
    return results


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from connect_etabs import attach_to_running_etabs, unlock_model
    from read_model import read_frame_objects, read_load_cases
    from modify_sections import snapshot_section_assignments

    etabs_obj, sap_model = attach_to_running_etabs()
    unlock_model(sap_model)

    frames       = read_frame_objects(sap_model)
    snapshot     = snapshot_section_assignments(frames)
    load_info    = read_load_cases(sap_model)

    # Identify load case names (adjust to match your model)
    all_cases = load_info['load_cases']
    modal_lc  = next((c for c in all_cases if 'MODAL' in c.upper()), "Modal")
    rs_x      = next((c for c in all_cases if 'RSX' in c.upper() or 'SX' in c.upper()), all_cases[0])
    rs_y      = next((c for c in all_cases if 'RSY' in c.upper() or 'SY' in c.upper()), all_cases[0])

    # Example design config — adjust group names to match your ETABS model
    test_config = {
        "Story3_Beams":   "B18x24",
        "Story3_Columns": "C24x24",
        "Story2_Beams":   "B18x24",
        "Story2_Columns": "C24x24",
        "Story1_Beams":   "B21x27",
        "Story1_Columns": "C30x30",
    }

    result = evaluate_design(
        sap_model     = sap_model,
        frames        = frames,
        section_snapshot = snapshot,
        design_config = test_config,
        analysis_cases = [modal_lc, rs_x, rs_y],
        modal_case     = modal_lc,
        seismic_x_case = rs_x,
        seismic_y_case = rs_y,
        drift_limit    = 0.020,
        run_design     = True,
    )

    import json
    # Print result (excluding per-story dicts for brevity)
    clean = {k: v for k, v in result.items()
             if k not in ('story_drifts_X', 'story_drifts_Y', 'design_config')}
    print("\nResult:", json.dumps(clean, indent=2, default=str))
