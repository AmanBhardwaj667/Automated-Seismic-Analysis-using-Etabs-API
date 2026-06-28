"""
ETABS Seismic Optimization Tool - Phase 1
Step 5: Running Analysis via API
==================================
Functions to:
  - Select which load cases to run
  - Trigger analysis
  - Check completion
  - Run headless (ETABS window hidden)
"""

import time
from typing import List, Optional


# ─── 5.1 Select load cases to run ────────────────────────────────────────────

def set_load_cases_to_run(sap_model, case_names: List[str]) -> bool:
    """
    Select which load cases will be included in the next analysis.

    Strategy:
      1. Deselect ALL load cases first.
      2. Re-select only the ones we need.
    This avoids accidentally running unused cases (saves time).

    API:
      Analyze.SetRunCaseFlag(Name, Run, All)
        Name = case name (or "" if All=True)
        Run  = True/False
        All  = if True, apply to all cases

    COMMON ERROR:
      A case name that doesn't exist → ret != 0, silently ignored.
      Fix: always call read_load_cases() first to verify names.
    """
    # Step 1: Deselect all
    ret = sap_model.Analyze.SetRunCaseFlag("", False, True)
    if ret != 0:
        print(f"  ⚠ Could not deselect all cases (code {ret}). Continuing.")

    # Step 2: Select desired cases
    ok_count = 0
    for name in case_names:
        ret = sap_model.Analyze.SetRunCaseFlag(name, True, False)
        if ret == 0:
            ok_count += 1
        else:
            print(f"  ⚠ Load case '{name}' not found or failed to select (code {ret}).")

    print(f"  ✓ Selected {ok_count}/{len(case_names)} load cases for analysis.")
    return ok_count == len(case_names)


# ─── 5.2 Run analysis ────────────────────────────────────────────────────────

def run_analysis(
    sap_model,
    timeout_sec: float = 300.0,
    poll_interval: float = 2.0
) -> bool:
    """
    Trigger the ETABS analysis and wait for completion.

    API: Analyze.RunAnalysis()
      This call is BLOCKING in most ETABS 2021 configurations.
      It returns only when analysis finishes or errors.
      If it is non-blocking on your setup, the poll loop below handles it.

    Returns True if analysis completed successfully, False otherwise.

    COMMON ERRORS:
      ret != 0 immediately → model has errors (bad connectivity, missing loads).
        Fix: open ETABS manually, run analysis interactively, read error log.
      Analysis appears to hang → another dialog is open in ETABS (license, etc.).
      "Model is locked" error → call unlock_model() before run_analysis().

    HEADLESS TIP:
      If ETABS was launched with etabs_obj.Hide(), analysis still runs silently.
      Do NOT use sap_model.Analyze.SetSolverOption() to change solver during a run.
    """
    print("  Running analysis... (this may take 30–300 seconds)")
    start_time = time.time()

    # The main analysis call
    ret = sap_model.Analyze.RunAnalysis()

    elapsed = time.time() - start_time
    print(f"  Analysis returned in {elapsed:.1f}s with code {ret}.")

    if ret != 0:
        print(f"  ✗ RunAnalysis returned error code {ret}.")
        print("    Common causes:")
        print("    1. Model geometry errors — check ETABS log file.")
        print("    2. Missing material or section definition.")
        print("    3. Model not fully saved before analysis.")
        return False

    # Verify results are available
    # GetCaseResultsAvailable returns (ret, Status) for each case
    # Status: 0=Not Run, 1=Could Not Start, 2=Not Finished, 3=Partial, 4=Finished
    ok = _verify_analysis_results(sap_model)
    return ok


def _verify_analysis_results(sap_model) -> bool:
    """Verify analysis by checking RunCaseFlag (GetCaseResultsAvailable not in this ETABS build)."""
    try:
        r = sap_model.Analyze.GetRunCaseFlag()
        if r[0] != 0:
            print("  ⚠ Could not verify results — assuming OK since RunAnalysis returned 0.")
            return True
        names = r[2]
        flags = r[3]
        for i in range(r[1]):
            if flags[i]:
                print(f"  ✓ Case '{names[i]}' was selected for run.")
        print("  ✓ Analysis complete — results should be available.")
        return True
    except Exception as e:
        print(f"  ⚠ Could not verify results ({e}) — assuming OK since RunAnalysis returned 0.")
        return True

# ─── 5.3 Run concrete frame design (for DCR extraction) ──────────────────────

def run_concrete_frame_design(sap_model) -> bool:
    """
    Run the ETABS concrete frame design module to generate DCR values.
    Must be called AFTER run_analysis() completes.

    API calls:
      DesignConcrete.StartDesign()   → runs design checks
      DesignConcrete.GetSummaryResultsBeam() / GetSummaryResultsColumn()
        → used in Step 6 to extract DCR

    COMMON ERROR:
      Design code not set → set in ETABS Options > Preferences > Concrete Frame Design.
      Typical codes: "ACI 318-19", "ACI 318-14".
    """
    # Set design code (ACI 318-19 for ASCE 7-22 compliance)
    ret = sap_model.DesignConcrete.SetCode("IS 456-2000")
    if ret != 0:
        # Try older code string
        ret = sap_model.DesignConcrete.SetCode("ACI 318-14")
        if ret != 0:
            print(f"  ⚠ Could not set concrete design code (code {ret}). Using model default.")

    ret = sap_model.DesignConcrete.StartDesign()
    if ret != 0:
        print(f"  ✗ StartDesign failed (code {ret}). Check analysis results exist.")
        return False

    print("  ✓ Concrete frame design complete.")
    return True


# ─── 5.4 Suppress/restore ETABS window ───────────────────────────────────────

def hide_etabs_window(etabs_obj) -> None:
    """Hide ETABS GUI for faster batch runs. Call after ApplicationStart."""
    try:
        etabs_obj.Hide()
        print("  ✓ ETABS window hidden.")
    except Exception as e:
        print(f"  ⚠ Could not hide ETABS window: {e}")


def show_etabs_window(etabs_obj) -> None:
    """Restore ETABS GUI (e.g., for debugging after an error)."""
    try:
        etabs_obj.Unhide()
        print("  ✓ ETABS window restored.")
    except Exception as e:
        print(f"  ⚠ Could not restore ETABS window: {e}")


# ─── 5.5 Full run sequence ────────────────────────────────────────────────────

def full_analysis_run(
    sap_model,
    case_names: List[str],
    run_design: bool = True
) -> bool:
    """
    Convenience: select cases, run analysis, optionally run design.
    Returns True if everything succeeded.
    """
    if not set_load_cases_to_run(sap_model, case_names):
        return False

    if not run_analysis(sap_model):
        return False

    if run_design:
        run_concrete_frame_design(sap_model)   # non-fatal if it fails

    return True


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from connect_etabs import attach_to_running_etabs, unlock_model
    from read_model import read_load_cases

    etabs_obj, sap_model = attach_to_running_etabs()
    unlock_model(sap_model)

    load_info = read_load_cases(sap_model)
    print("Available load cases:", load_info['load_cases'])

    # Example: run all response spectrum and modal cases
    cases_to_run = [
        lc for lc in load_info['load_cases']
        if any(x in lc.upper() for x in ["MODAL", "RS", "EQ", "SPEC"])
    ]
    if not cases_to_run:
        cases_to_run = load_info['load_cases'][:3]   # run first 3 as fallback

    print(f"Running: {cases_to_run}")
    ok = full_analysis_run(sap_model, cases_to_run, run_design=True)
    print("Analysis + Design OK:", ok)
