# ETABS Seismic Optimization — Phase 1
# Common Errors Reference & Completion Checklist
# ================================================


# ══════════════════════════════════════════════════════════════════════
# COMMON ERRORS AND EXACT FIXES
# ══════════════════════════════════════════════════════════════════════

ERRORS = """
ERROR 1: "Class not registered" / OSError when calling comtypes.client.GetActiveObject()
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  64-bit Python is being used. ETABS COM objects are 32-bit only.
FIX:    Uninstall current Python, install Python 3.9.x (x86) from python.org.
        Confirm with: python -c "import sys; print(sys.maxsize > 2**32)"
        Must print False.

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 2: "Call was rejected by callee" (RPC_E_CALL_REJECTED)
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  ETABS has a modal dialog open (message box, license warning, etc.)
FIX:    Click away any dialogs in ETABS, then retry.
        If running headless: launch ETABS fully before attaching.

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 3: SetRectangle() returns non-zero / "material not found"
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  Material name string doesn't exactly match what's in the model.
FIX:    Run: names = sap_model.PropMaterial.GetNameList()
             print(names[2])   # list all defined materials
        Then update CONFIG['concrete_mat'] and CONFIG['rebar_mat'] to match exactly.
        Common names: "4000Psi", "C4000", "NW 4000psi", "Grade 60", "A615Gr60"

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 4: SetModelIsLocked(False) returns non-zero
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  Analysis results windows are open in ETABS.
FIX:    Close all results displays in ETABS (Display menu → close results).
        Then retry unlock_model().

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 5: RunAnalysis() returns 0 but GetCaseResultsAvailable shows "Not Run"
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  SetRunCaseFlag() was not called, or the case name is wrong.
FIX:    1. Double-check case names: print(sap_model.LoadCases.GetNameList()[2])
        2. Names are case-sensitive: "Modal" ≠ "modal" ≠ "MODAL"
        3. Ensure analysis cases are correctly defined in ETABS.

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 6: StoryDrifts() returns empty / num == 0
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE A: Wrong load case selected for output.
  FIX:  Verify the exact case name. RS/spectrum cases need to have run successfully.
CAUSE B: Story drift output not enabled for the load case.
  FIX:  In ETABS, go to Display > Show Tables > Analysis Results > Story Drifts
        If table is empty there too, drift calculation may not be enabled.
        Check Analyze > Set Load Cases to Run — ensure case has results.

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 7: DesignConcrete.GetSummaryResultsBeam() returns ret != 0
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  The frame is a column, not a beam (or vice versa).
FIX:    Use get_column_dcr() for columns, get_beam_dcr() for beams.
        Or check: sap_model.FrameObj.GetDesignProcedure(name)
          Returns (ret, ProcType) where ProcType: 1=Steel, 2=Concrete, 3=Aluminum

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 8: FrameObj.SetSection(group_name, section, "", 1) returns non-zero
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  Group not defined in the model.
FIX:    Create groups in ETABS: Select members → Assign → Assign to Group → New Group.
        Or use the story+type fallback in apply_design_config().
        List existing groups: sap_model.GroupDef.GetNameList()

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 9: comtypes generates a wrong/stale wrapper (AttributeError on methods)
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  Old comtypes cache from a previous ETABS version.
FIX:    Delete the comtypes cache:
          import comtypes.client
          comtypes.client.GetModule.cache.clear()   # if available
        Or manually delete: %LOCALAPPDATA%\\comtypes_cache\\  (delete all subfolders)
        Then restart Python and reimport.

──────────────────────────────────────────────────────────────────────────────────────────
ERROR 10: Analysis completes but drifts seem wrong (too small or too large)
──────────────────────────────────────────────────────────────────────────────────────────
CAUSE:  Units mismatch. StoryDrifts() returns the drift RATIO, not absolute displacement.
        If it returns large numbers (like 5000), units are set to inches and you're
        reading displacement, not ratio.
FIX:    Call sap_model.SetPresentUnits(7) for kip-in before reading results.
        Confirm: drift ratio should be 0.001–0.030 for typical buildings.
        If GetDrifts is unavailable in your ETABS version, compute manually:
          delta = story_displacement - story_below_displacement
          drift_ratio = delta / story_height

"""


# ══════════════════════════════════════════════════════════════════════
# SUGGESTED FOLDER STRUCTURE
# ══════════════════════════════════════════════════════════════════════

FOLDER_STRUCTURE = """
your_project/
│
├── etabs_api/                        ← All Python source files
│   ├── 01_environment_setup.py
│   ├── 02_connect_etabs.py
│   ├── 03_read_model.py
│   ├── 04_modify_sections.py
│   ├── 05_run_analysis.py
│   ├── 06_extract_results.py
│   ├── 07_evaluate_design.py
│   ├── 08_logging.py
│   ├── 09_master_run.py
│   └── 10_errors_and_checklist.py
│
├── results/                           ← Auto-created by logging module
│   ├── seismic_opt_YYYYMMDD_HHMMSS.xlsx
│   ├── best_designs.xlsx
│   └── model_snapshot.json
│
├── models/                            ← Your ETABS model files
│   └── MyBuilding.EDB
│
├── phase2/                            ← Phase 2 optimizer (future)
│   └── (placeholder)
│
├── .vscode/
│   └── settings.json                  ← VS Code interpreter config
│
└── requirements.txt
"""


# ══════════════════════════════════════════════════════════════════════
# VS CODE SETUP
# ══════════════════════════════════════════════════════════════════════

VSCODE_SETTINGS = """
// .vscode/settings.json
// Set to your 32-bit Python 3.9 interpreter path
{
    "python.defaultInterpreterPath": "C:\\\\Python39-32\\\\python.exe",
    "python.analysis.extraPaths": ["."],
    "editor.rulers": [88],
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "files.autoSave": "afterDelay",
    "files.autoSaveDelay": 5000
}

Recommended VS Code Extensions:
  - Python (Microsoft)
  - Pylance
  - Excel Viewer (for .xlsx previews)
  - GitLens (optional, for versioning your configs)

IMPORTANT: In VS Code bottom-left, click the Python interpreter selector
and choose your 32-bit Python 3.9 installation. If it doesn't appear,
click "Enter interpreter path" and browse to C:\\Python39-32\\python.exe
"""


REQUIREMENTS_TXT = """
# requirements.txt — install with: pip install -r requirements.txt
comtypes==1.2.0
numpy==1.24.4
pandas==2.0.3
scipy==1.11.4
openpyxl==3.1.2
XlsxWriter==3.1.9
matplotlib==3.7.4
tqdm==4.66.1
"""


# ══════════════════════════════════════════════════════════════════════
# PHASE 1 COMPLETION CHECKLIST
# ══════════════════════════════════════════════════════════════════════

CHECKLIST = """
╔══════════════════════════════════════════════════════════════════════╗
║          PHASE 1 COMPLETION CHECKLIST                               ║
╚══════════════════════════════════════════════════════════════════════╝

ENVIRONMENT
  [ ] Python 3.9.x (32-bit) installed and selected in VS Code
  [ ] All packages installed: comtypes, numpy, pandas, scipy, openpyxl
  [ ] 01_environment_setup.py runs with all ✓ green

ETABS CONNECTION (Step 2)
  [ ] ETABS 2021 open with File → API → Allow ETABS API Access checked
  [ ] 02_connect_etabs.py attaches successfully (prints ✓ Attached)
  [ ] unlock_model() returns 0
  [ ] Model filename printed correctly
  [ ] Units successfully set to kip-in (enum 7)

READ MODEL (Step 3)
  [ ] read_frame_sections() returns correct count of sections
  [ ] All section types read (Rectangular confirmed for RC sections)
  [ ] read_frame_objects() returns correct beam/column count
  [ ] Beams and columns correctly identified (check depth/width values)
  [ ] read_story_data() returns correct story names and heights
  [ ] read_load_cases() returns your actual load case names
  [ ] Load case names EXACTLY match those in ETABS (case-sensitive)

MODIFYING SECTIONS (Step 4)
  [ ] snapshot_section_assignments() captures all frame sections
  [ ] define_rc_rect_section() creates "TEST_B18x24" without error
  [ ] assign_section_to_frame() assigns to one frame, ret=0
  [ ] restore_section_assignments() restores original sections
  [ ] ETABS shows original sections restored (verify visually)
  [ ] define_section_library() creates all candidate sections successfully

RUNNING ANALYSIS (Step 5)
  [ ] set_load_cases_to_run() selects Modal + RS cases, returns True
  [ ] run_analysis() completes without error (ret=0)
  [ ] _verify_analysis_results() shows at least one "Finished" case
  [ ] run_concrete_frame_design() completes (StartDesign ret=0)

EXTRACTING RESULTS (Step 6)
  [ ] get_story_drifts() returns values between 0.001 and 0.030
  [ ] Drift ratios (not absolute displacements) confirmed
  [ ] get_base_shear() returns non-zero Vx and Vy values
  [ ] get_modal_results() returns T1 > 0
  [ ] SumUX and SumUY both > 80% (sufficient modes)
  [ ] get_beam_dcr() returns dict without error for one beam
  [ ] get_column_dcr() returns pmm_dcr > 0 for one column

EVALUATE DESIGN (Step 7)
  [ ] evaluate_design() completes one full cycle without exception
  [ ] All result keys present in returned dict
  [ ] overall_pass correctly reflects drift and DCR checks
  [ ] Run time is reasonable (< 5 min for full analysis + design)
  [ ] Restore works after evaluation (check ETABS sections unchanged)

LOGGING (Step 8)
  [ ] RunLogger.log() stores all result fields
  [ ] Auto-save triggers every N runs (check file created)
  [ ] Excel file opens correctly and shows all columns
  [ ] Failing rows highlighted in red
  [ ] save_best() correctly ranks passing designs

MASTER RUN (Step 9)
  [ ] 09_master_run.py completes end-to-end without errors
  [ ] results/ folder created with Excel file and JSON snapshot
  [ ] model_snapshot.json contains section names, stories, load cases
  [ ] At least 1 run logged to Excel

READY FOR PHASE 2 WHEN:
  [ ] All items above checked ✓
  [ ] evaluate_design() called at least 5 times successfully
  [ ] Log file contains consistent data for all runs
  [ ] You know the exact group/story naming convention for your model
  [ ] T1 and story drifts match your manual ETABS check (sanity verified)
"""

if __name__ == "__main__":
    print(CHECKLIST)
    print(ERRORS[:500] + "\n... (run this file to print full error guide)")
    print(FOLDER_STRUCTURE)
