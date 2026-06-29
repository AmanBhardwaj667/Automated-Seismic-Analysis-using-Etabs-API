"""
ETABS Seismic Optimization Tool - Phase 1
Step 6: Extracting Results via API
====================================
Functions to extract:
  - Modal results (periods, mass participation)
  - Story drifts (X and Y per story)
  - Base shear (X and Y)
  - Frame member forces (M, V, N)
  - DCR from concrete frame design

ETABS API convention (confirmed):
  Get* -> ret code is LAST element: r[-1]
  Set* -> ret code is plain int: r

ModalParticipatingMassRatios CORRECTED tuple layout (18 elements, confirmed
by runtime debug on this build/version of ETABS):
  r[0]  = count (int)
  r[1]  = LoadCase names tuple
  r[2]  = StepType tuple
  r[3]  = StepNum tuple
  r[4]  = Eigenvalue tuple (rad^2/s^2) -- NOT Period directly!
          Period = 2*pi / sqrt(Eigenvalue)
  r[5]  = UX tuple
  r[6]  = UY tuple
  r[7]  = UZ tuple
  r[8]  = SumUX tuple
  r[9]  = SumUY tuple
  r[10] = SumUZ tuple
  r[11] = RX, r[12]=RY, r[13]=RZ
  r[14] = SumRX, r[15]=SumRY, r[16]=SumRZ
  r[-1] = ret code (int)

(The original docstring assumed r[0]=LoadCase and r[16]=count with Period
at r[3]; runtime debug showed this build instead returns count at r[0] and
Eigenvalue (not Period) at r[4]. Confirmed via direct field dump -- see
DEBUG prints below, which can be removed once you're confident.)
"""

import math
from typing import Dict, List, Optional, Tuple


# ─── 6.1 Modal Results ───────────────────────────────────────────────────────

def get_modal_results(sap_model, modal_case_name: str = "Modal", debug: bool = False) -> Dict:
    """
    Returns modal periods and mass participation ratios.

    See module docstring for the confirmed tuple layout for this ETABS build.
    """
    sap_model.Results.Setup.DeselectAllCasesAndCombosForOutput()
    ret = sap_model.Results.Setup.SetCaseSelectedForOutput(modal_case_name)
    if ret != 0:
        print(f"  ⚠ Modal case '{modal_case_name}' not found (ret={ret}).")
        return {}

    r = sap_model.Results.ModalParticipatingMassRatios()

    if debug:
        print("DEBUG count r[0]:", r[0])
        for idx in range(1, 17):
            print(f"DEBUG r[{idx}][0:3] =", r[idx][:3])

    # ret code is last element
    if r[-1] != 0:
        print(f"  ⚠ ModalParticipatingMassRatios failed: ret={r[-1]}")
        return {}

    num = r[0]
    if num == 0:
        print(f"  ⚠ No modal results in case '{modal_case_name}'.")
        return {}

    eigenvalues = r[4]
    periods = tuple(
        2 * math.pi / math.sqrt(ev) if ev > 0 else 0.0 for ev in eigenvalues
    )
    UX    = r[5]
    UY    = r[6]
    SumUX = r[8]
    SumUY = r[9]

    modes = []
    for i in range(num):
        modes.append({
            'mode':   i + 1,
            'period': periods[i],
            'UX':     UX[i],
            'UY':     UY[i],
            'SumUX':  SumUX[i],
            'SumUY':  SumUY[i],
        })

    result = {
        'T1':        periods[0] if num >= 1 else 0.0,
        'T2':        periods[1] if num >= 2 else 0.0,
        'T3':        periods[2] if num >= 3 else 0.0,
        'UX1':       UX[0]      if num >= 1 else 0.0,
        'UY1':       UY[0]      if num >= 1 else 0.0,
        'SumUX':     SumUX[-1]  if num >= 1 else 0.0,
        'SumUY':     SumUY[-1]  if num >= 1 else 0.0,
        'modes':     modes,
        'num_modes': num,
    }
    return result


# ─── 6.2 Story Drifts ────────────────────────────────────────────────────────

def get_story_drifts(sap_model, load_case: str, direction: str = "X") -> Dict[str, float]:
    """
    Returns {story_name: max_drift_ratio} for the given load case and direction.
    Drift ratio = inter-story drift / story height (dimensionless).

    StoryDrifts tuple (ret code last):
      r[0]=count, r[1]=Story, r[2]=LoadCase, r[3]=StepType, r[4]=StepNum,
      r[5]=Direction, r[6]=Drift, r[7]=Label, r[8]=X, r[9]=Y, r[10]=Z,
      r[-1]=ret
    """
    sap_model.Results.Setup.DeselectAllCasesAndCombosForOutput()
    ret = sap_model.Results.Setup.SetCaseSelectedForOutput(load_case)
    if ret != 0:
        print(f"  ⚠ Could not select '{load_case}' for output (ret={ret}).")
        return {}

    r = sap_model.Results.StoryDrifts()
    if r[-1] != 0 or r[0] == 0:
        print(f"  ⚠ No story drift results for '{load_case}'.")
        return {}

    num        = r[0]
    stories    = r[1]
    directions = r[5]
    drifts     = r[6]

    result = {}
    dir_upper = direction.upper()
    for i in range(num):
        if str(directions[i]).upper() == dir_upper:
            story = stories[i]
            drift = abs(drifts[i])
            if story not in result or drift > result[story]:
                result[story] = drift
    return result


def get_all_story_drifts(sap_model, load_case: str) -> Dict[str, Dict[str, float]]:
    """Returns {'X': {story: drift}, 'Y': {story: drift}}"""
    return {
        'X': get_story_drifts(sap_model, load_case, "X"),
        'Y': get_story_drifts(sap_model, load_case, "Y"),
    }


# ─── 6.3 Base Shear ──────────────────────────────────────────────────────────

def get_base_shear(sap_model, load_case: str) -> Dict[str, float]:
    """
    Returns {'Vx': kips, 'Vy': kips} base shear.

    BaseReact tuple (ret code last):
      r[0]=count, r[1]=LoadCase, r[2]=StepType, r[3]=StepNum,
      r[4]=Fx, r[5]=Fy, r[6]=Fz, r[7]=Mx, r[8]=My, r[9]=Mz,
      r[10]=GlobalX, r[11]=GlobalY, r[12]=GlobalZ, r[-1]=ret
    """
    sap_model.Results.Setup.DeselectAllCasesAndCombosForOutput()
    sap_model.Results.Setup.SetCaseSelectedForOutput(load_case)

    r = sap_model.Results.BaseReact()
    if r[-1] != 0 or r[0] == 0:
        print(f"  ⚠ No base reaction results for '{load_case}'.")
        return {'Vx': 0.0, 'Vy': 0.0}

    num = r[0]
    Fx_vals = [abs(r[4][i]) for i in range(num)]
    Fy_vals = [abs(r[5][i]) for i in range(num)]

    return {
        'Vx': max(Fx_vals) if Fx_vals else 0.0,
        'Vy': max(Fy_vals) if Fy_vals else 0.0,
    }


# ─── 6.4 Frame Member Forces ─────────────────────────────────────────────────

def get_frame_forces(sap_model, frame_unique_name: str, load_case: str) -> Dict[str, float]:
    """
    Returns max/min M3, V2, P (axial) for one frame member.

    FrameForce tuple (ret code last):
      r[0]=count, r[1]=Obj, r[2]=ObjSta, r[3]=Elm, r[4]=ElmSta,
      r[5]=LoadCase, r[6]=StepType, r[7]=StepNum,
      r[8]=P, r[9]=V2, r[10]=V3, r[11]=T, r[12]=M2, r[13]=M3,
      r[-1]=ret
    """
    sap_model.Results.Setup.DeselectAllCasesAndCombosForOutput()
    sap_model.Results.Setup.SetCaseSelectedForOutput(load_case)

    r = sap_model.Results.FrameForce(frame_unique_name, 0, 0)
    if r[-1] != 0 or r[0] == 0:
        return {'P_max': 0, 'V2_max': 0, 'M3_max': 0, 'P_min': 0, 'M3_min': 0}

    num = r[0]
    P  = [r[8][i]  for i in range(num)]
    V2 = [r[9][i]  for i in range(num)]
    M3 = [r[13][i] for i in range(num)]

    return {
        'P_max':  max(P),
        'P_min':  min(P),
        'V2_max': max(abs(v) for v in V2),
        'M3_max': max(M3),
        'M3_min': min(M3),
    }


# ─── 6.5 DCR from Concrete Frame Design ──────────────────────────────────────

def get_beam_dcr(sap_model, frame_unique_name: str) -> Dict:
    """
    Returns beam rebar areas after concrete frame design.
    Requires run_concrete_frame_design() first.

    GetSummaryResultsBeam tuple (ret code last):
      r[0]=FrameName, r[1]=Combo, r[2]=Location,
      r[3]=TopCombo, r[4]=TopArea,
      r[5]=BotCombo, r[6]=BotArea,
      r[7]=VMajorCombo, r[8]=VMajorArea,
      r[9]=TorsionCombo, r[10]=TorsionArea,
      r[11]=ErrorSummary, r[12]=WarnSummary,
      r[-1]=ret
    """
    r = sap_model.DesignConcrete.GetSummaryResultsBeam(frame_unique_name)
    if r[-1] != 0:
        return {'top_rebar_area_in2': 0.0, 'bot_rebar_area_in2': 0.0,
                'shear_rebar_in2_per_in': 0.0, 'design_ok': False, 'error_msg': ''}

    top_area   = r[4]  if len(r) > 4  else 0.0
    bot_area   = r[6]  if len(r) > 6  else 0.0
    shear_area = r[8]  if len(r) > 8  else 0.0
    error_msg  = r[11] if len(r) > 11 else ""
    design_ok  = (not error_msg) or (str(error_msg).strip() == "")

    return {
        'top_rebar_area_in2':     top_area,
        'bot_rebar_area_in2':     bot_area,
        'shear_rebar_in2_per_in': shear_area,
        'design_ok':              design_ok,
        'error_msg':              error_msg,
    }


def get_column_dcr(sap_model, frame_unique_name: str) -> Dict:
    """
    Returns column PMM DCR after concrete frame design.

    GetSummaryResultsColumn tuple (ret code last):
      r[0]=FrameName,
      r[1]=MyCombo, r[2]=MyEqLength, r[3]=MyFactor,
      r[4]=MzCombo, r[5]=MzEqLength, r[6]=MzFactor,
      r[7]=PmmCombo, r[8]=PmmRatio, r[9]=PmmArea,
      r[10]=VmajorCombo, r[11]=VmajorArea,
      r[12]=VminorCombo, r[13]=VminorArea,
      r[14]=ErrorSummary, r[15]=WarnSummary,
      r[-1]=ret
    """
    r = sap_model.DesignConcrete.GetSummaryResultsColumn(frame_unique_name)
    if r[-1] != 0:
        return {'pmm_dcr': -1.0, 'rebar_area_in2': 0.0, 'design_ok': False, 'error_msg': ''}

    pmm_ratio = r[8]  if len(r) > 8  else 999.0
    pmm_area  = r[9]  if len(r) > 9  else 0.0
    error_msg = r[14] if len(r) > 14 else ""
    design_ok = (pmm_ratio <= 1.0) and (not error_msg or str(error_msg).strip() == "")

    return {
        'pmm_dcr':        pmm_ratio,
        'rebar_area_in2': pmm_area,
        'design_ok':      design_ok,
        'error_msg':      error_msg,
    }


def get_max_dcr_all_frames(sap_model, frames: list) -> Dict:
    """
    Scan all frames, return global max DCR values.
    Key function called by evaluate_design() in Step 7.
    """
    max_col_pmm  = 0.0
    max_beam_top = 0.0
    n_beam_fail  = 0
    n_col_fail   = 0

    for f in frames:
        if f.obj_type == "Beam":
            d = get_beam_dcr(sap_model, f.unique_name)
            if not d['design_ok']:
                n_beam_fail += 1
            if d['top_rebar_area_in2'] > max_beam_top:
                max_beam_top = d['top_rebar_area_in2']
        elif f.obj_type == "Column":
            d = get_column_dcr(sap_model, f.unique_name)
            if d['pmm_dcr'] > max_col_pmm:
                max_col_pmm = d['pmm_dcr']
            if not d['design_ok']:
                n_col_fail += 1

    print(f"  DCR scan: max col PMM={max_col_pmm:.3f}, "
          f"beam fails={n_beam_fail}, col fails={n_col_fail}")

    return {
        'max_col_pmm_dcr':    max_col_pmm,
        'max_beam_rebar_in2': max_beam_top,
        'n_beam_design_fail': n_beam_fail,
        'n_col_design_fail':  n_col_fail,
        'any_design_fail':    (n_beam_fail + n_col_fail) > 0,
    }


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from connect_etabs import attach_to_running_etabs, unlock_model
    from read_model import read_load_cases

    etabs_obj, sap_model = attach_to_running_etabs()

    load_info = read_load_cases(sap_model)
    print("Load cases:", load_info['load_cases'])

    # IMPORTANT: RunAnalysis() only re-runs cases that are flagged to run.
    # If a case (e.g. "Dead") was never flagged, RunAnalysis() can still
    # return 0 (success) while that case has zero results. Always confirm
    # the cases you need are flagged before running.
    for case_name in ["Dead", "Live", "Modal", "CP + FF", "Wall",
                       "~LLRF", "~ChineseX", "~ChineseY"]:
        sap_model.Analyze.SetRunCaseFlag(case_name, True)

    sap_model.File.Save()
    ret = sap_model.Analyze.RunAnalysis()
    print("RunAnalysis ret:", ret)

    # Test modal
    print("\n── Modal Results ──")
    modal = get_modal_results(sap_model, "Modal", debug=False)
    if modal:
        print(f"  T1={modal['T1']:.3f}s  T2={modal['T2']:.3f}s  T3={modal['T3']:.3f}s")
        print(f"  SumUX={modal['SumUX']:.1%}  SumUY={modal['SumUY']:.1%}")
        print(f"  Num modes: {modal['num_modes']}")
        for m in modal['modes'][:3]:
            print(f"    Mode {m['mode']}: T={m['period']:.3f}s  UX={m['UX']:.3f}  UY={m['UY']:.3f}")
    else:
        print("  No modal results returned.")

    # Test base shear on Dead case (always has results)
    print("\n── Base Shear (Dead) ──")
    shear = get_base_shear(sap_model, "Dead")
    print(f"  Vx={shear['Vx']:.3f} kip  Vy={shear['Vy']:.3f} kip")

    # Test story drifts on Dead case
    print("\n── Story Drifts (Dead) ──")
    drifts = get_all_story_drifts(sap_model, "Dead")
    for story in drifts['X']:
        print(f"  {story}: X={drifts['X'][story]:.6f}  Y={drifts['Y'].get(story,0):.6f}")
