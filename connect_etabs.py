"""
ETABS Seismic Optimization Tool - Phase 1
Step 2: Connecting to ETABS via comtypes
=========================================

ETABS-SIDE PREREQUISITES (do these ONCE before running any script):
1. Open ETABS 2021.
2. Go to File → API → Allow ETABS API Access (must be checked).
3. Have a model open (locked or unlocked — the API can unlock it).
4. Make sure no modal dialogs are open in ETABS.

COM SERVER REGISTRATION:
  ETABS 2021 registers itself automatically on install.
  If it fails: run ETABS as Administrator once, or manually run:
    regsvr32 "C:\\Program Files\\Computers and Structures\\ETABS 21\\ETABS.exe"
  (Not usually needed.)
"""

import sys
import os
import comtypes.client

# ─── Constants ───────────────────────────────────────────────────────────────
ETABS_PROG_ID  = "CSI.ETABS.API.ETABSObject"   # ETABS 2021 ProgID
ETABS_EXE_PATH = r"C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe"


def attach_to_running_etabs():
    """
    Attach to an already-running ETABS 2021 instance.
    Returns (etabs_object, sap_model) or raises RuntimeError.

    COMMON ERRORS:
      OSError / "Class not registered"  → ETABS not installed, or 64-bit Python used.
      "Call was rejected by callee"      → A dialog box is open in ETABS. Close it.
      AttributeError on SapModel        → Wrong ProgID or old ETABS version.
    """
    try:
        helper = comtypes.client.CreateObject("ETABSv1.Helper")
        helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
    except Exception:
        # Fallback: use the generic ProgID approach
        helper = None

    try:
        if helper is not None:
            etabs_obj = helper.GetObject("CSI.ETABS.API.ETABSObject")
        else:
            etabs_obj = comtypes.client.GetActiveObject(ETABS_PROG_ID)
    except OSError as e:
        raise RuntimeError(
            "Cannot attach to ETABS. Ensure:\n"
            "  1. ETABS 2021 is running.\n"
            "  2. File → API → 'Allow ETABS API Access' is checked.\n"
            "  3. No modal dialogs are open.\n"
            "  4. You are using 32-bit Python.\n"
            f"Original error: {e}"
        ) from e

    sap_model = etabs_obj.SapModel
    if sap_model is None:
        raise RuntimeError("Connected to ETABS but SapModel is None. Is a model open?")

    print("✓ Attached to running ETABS instance.")
    return etabs_obj, sap_model


def launch_and_attach_etabs(exe_path=ETABS_EXE_PATH, visible=True):
    """
    Launch a new ETABS instance from Python, then attach to it.
    Use this when you want full headless control from script start.

    visible=False → hides the ETABS window (faster for batch runs).
    Returns (etabs_object, sap_model).
    """
    if not os.path.exists(exe_path):
        raise FileNotFoundError(
            f"ETABS executable not found at:\n  {exe_path}\n"
            "Update ETABS_EXE_PATH in this file."
        )

    try:
        helper = comtypes.client.CreateObject("ETABSv1.Helper")
        helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
        etabs_obj = helper.CreateObject(exe_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to launch ETABS from {exe_path}.\n"
            f"Try running as Administrator.\nError: {e}"
        ) from e

    etabs_obj.ApplicationStart()
    sap_model = etabs_obj.SapModel

    # Set GUI visibility
    sap_model.SetModelIsLocked(False)          # Unlock immediately
    ret = sap_model.GetModelFilename()         # Just to test connection
    if not visible:
        # Hide the main window (call after ApplicationStart)
        etabs_obj.Hide()
    print(f"✓ Launched ETABS ({'hidden' if not visible else 'visible'}).")
    return etabs_obj, sap_model


def open_model(sap_model, edb_path: str) -> None:
    """
    Open a specific .edb file. Model must already be running.
    edb_path: full absolute path, e.g. r"C:\\Projects\\MyBuilding.EDB"

    COMMON ERRORS:
      ret != 0   → File not found, or model already open.
      Model stays locked after open → call unlock_model() below.
    """
    if not os.path.isfile(edb_path):
        raise FileNotFoundError(f"Model file not found: {edb_path}")

    ret = sap_model.File.OpenFile(edb_path)
    if ret != 0:
        raise RuntimeError(
            f"OpenFile returned error code {ret} for:\n  {edb_path}\n"
            "Check: file not already open in another ETABS instance."
        )
    print(f"✓ Opened model: {edb_path}")


def unlock_model(sap_model) -> None:
    """
    Unlock the model for editing. Always call before modifying sections.
    ETABS locks a model after analysis — you must unlock before changes.

    COMMON ERROR:
      ret != 0 after analysis  → Model is in post-analysis state.
      Fix: sap_model.SetModelIsLocked(False) is the correct call.
    """
    ret = sap_model.SetModelIsLocked(False)
    if ret != 0:
        raise RuntimeError(
            f"SetModelIsLocked(False) returned {ret}. "
            "Try closing results windows in ETABS first."
        )
    print("✓ Model unlocked for editing.")


def disconnect_etabs(etabs_obj, sap_model, save=False, save_path=None) -> None:
    """
    Safely disconnect from ETABS.
    save=True → saves the model before disconnecting.
    """
    if save:
        path = save_path or sap_model.GetModelFilename(False)
        ret = sap_model.File.Save(path)
        if ret != 0:
            print(f"  ⚠ Save returned code {ret}. Check file path.")
        else:
            print(f"  ✓ Model saved: {path}")

    # Release COM object — do NOT call ApplicationExit() unless you own the instance
    del sap_model
    del etabs_obj
    print("✓ Disconnected from ETABS.")


# ─── Quick connection helper used by all other modules ───────────────────────

def get_sap_model(edb_path=None, launch=False, visible=True):
    """
    Convenience function:
      - If launch=True: start a new ETABS instance.
      - Otherwise: attach to running instance.
      - If edb_path given: open that model.
    Returns (etabs_obj, sap_model).
    """
    if launch:
        etabs_obj, sap_model = launch_and_attach_etabs(visible=visible)
    else:
        etabs_obj, sap_model = attach_to_running_etabs()

    if edb_path:
        open_model(sap_model, edb_path)

    unlock_model(sap_model)
    return etabs_obj, sap_model


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run this with ETABS 2021 open and a model loaded.
    Expected output: ✓ Attached ... ✓ Model unlocked ... Model filename: ...
    """
    etabs_obj, sap_model = attach_to_running_etabs()
    unlock_model(sap_model)

    filename = sap_model.GetModelFilename(False)
    print(f"  Model filename: {filename}")

    units = sap_model.GetPresentUnits()
    # Units enum: 6 = kip-ft, 7 = kip-in, 10 = kN-m (most common for API work)
    print(f"  Current units enum: {units}")

    # Set units to kip-in for ASCE 7 checks (common US practice)
    # eForce_Kip=4, eLength_in=2 → combined unit enum 7
    sap_model.SetPresentUnits(7)    # kip-in
    print("  ✓ Units set to kip-in")

    disconnect_etabs(etabs_obj, sap_model, save=False)
