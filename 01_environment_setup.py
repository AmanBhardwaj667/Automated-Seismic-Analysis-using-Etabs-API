"""
ETABS Seismic Optimization Tool - Phase 1
Step 1: Environment Setup & Verification
=========================================
Run this script FIRST to verify your environment is correctly configured.
"""

import sys
import importlib

# ─── Python Version Check ────────────────────────────────────────────────────
# ETABS 2021 OAPI requires 32-bit Python 3.7–3.10.
# comtypes and the CSI COM objects are 32-bit only on Windows.
# RECOMMENDATION: Use Python 3.9.x (32-bit) — best balance of comtypes
# stability and modern library support.
# Download: https://www.python.org/downloads/release/python-3913/
#   → Windows installer (32-bit) → "Windows installer (x86)"

def check_python():
    major, minor = sys.version_info[:2]
    bits = 64 if sys.maxsize > 2**32 else 32
    print(f"Python {major}.{minor} ({bits}-bit)")
    if bits != 32:
        print("  ✗ ERROR: You need 32-bit Python. ETABS COM objects are 32-bit.")
        print("    Download Python 3.9 x86 from python.org")
        return False
    if not (major == 3 and 7 <= minor <= 10):
        print(f"  ✗ WARNING: Python 3.7–3.10 recommended. You have {major}.{minor}")
    else:
        print("  ✓ Python version OK")
    return True

REQUIRED_PACKAGES = {
    "comtypes":   "pip install comtypes==1.2.0",
    "numpy":      "pip install numpy==1.24.4",
    "pandas":     "pip install pandas==2.0.3",
    "scipy":      "pip install scipy==1.11.4",
    "openpyxl":   "pip install openpyxl==3.1.2",
    "xlsxwriter": "pip install XlsxWriter==3.1.9",
    "matplotlib": "pip install matplotlib==3.7.4",
    "tqdm":       "pip install tqdm==4.66.1",
}

def check_packages():
    all_ok = True
    for pkg, install_cmd in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg} MISSING → run: {install_cmd}")
            all_ok = False
    return all_ok

if __name__ == "__main__":
    print("=" * 60)
    print("ETABS Phase 1 — Environment Check")
    print("=" * 60)
    py_ok = check_python()
    print("\nPackage availability:")
    pkg_ok = check_packages()
    print()
    if py_ok and pkg_ok:
        print("✓ Environment ready. Proceed to 02_connect_etabs.py")
    else:
        print("✗ Fix the issues above before continuing.")
