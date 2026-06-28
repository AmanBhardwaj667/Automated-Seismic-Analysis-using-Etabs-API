"""
ETABS Seismic Optimization Tool - Phase 1
Step 4: Define RCC Materials & Sections, Reassign Frames
Units: kip-in (model unit enum = 9).
ETABS API convention:
  Get* -> ret is last element: r[-1]
  Set* -> ret is plain int: r
"""

from connect_etabs import attach_to_running_etabs, unlock_model

MM2IN   = 1.0 / 25.4
MPA2KSI = 1.0 / 6.894757

CONCRETE_GRADES = {
    'M20': 20, 'M25': 25, 'M30': 30,
    'M35': 35, 'M40': 40, 'M45': 45,
}

REBAR_LONG = 'Fe500'
REBAR_TIES = 'Fe415'
COLUMN_SIZES_MM = [300, 400, 450, 500, 600]
BEAM_SIZES_MM = {300: 450, 400: 500, 450: 600, 500: 700, 600: 750}
BEAM_COVER_MM = 40.0
START_COL_SECTION  = 'C300x300-M25'
START_BEAM_SECTION = 'B300x450-M25'
OLD_SECTIONS = ['ISWB550', 'ISLB600', 'beam300*400', 'beam300*500', 'Column300*300']


def define_concrete_materials(sap_model) -> list:
    defined = []
    for grade, fc_mpa in CONCRETE_GRADES.items():
        fc_ksi = float(fc_mpa * MPA2KSI)
        r = sap_model.PropMaterial.SetMaterial(grade, 2)
        if r != 0:
            print(f"  ⚠ SetMaterial({grade}) failed: ret={r}")
            continue
        r = sap_model.PropMaterial.SetOConcrete_1(
            grade, fc_ksi, False, 1.0, 0, 0, -0.003, -0.005, 0.0, 0.0)
        if r != 0:
            print(f"  ⚠ SetOConcrete_1({grade}) failed: ret={r}")
            continue
        E_mpa = 5000.0 * (fc_mpa ** 0.5)
        E_ksi = float(E_mpa * MPA2KSI)
        r = sap_model.PropMaterial.SetMPIsotropic(grade, E_ksi, 0.2, 9.9e-6)
        if r != 0:
            print(f"  ⚠ SetMPIsotropic({grade}) failed: ret={r}")
        defined.append(grade)
        print(f"  ✓ {grade}: fc={fc_mpa} MPa ({fc_ksi:.4f} ksi), E={E_mpa:.0f} MPa ({E_ksi:.2f} ksi)")
    return defined


def define_rebar_materials(sap_model) -> list:
    rebar_props = {
        'Fe500': {'fy': 500, 'fu': 545, 'E': 200000},
        'Fe415': {'fy': 415, 'fu': 485, 'E': 200000},
    }
    defined = []
    for name, props in rebar_props.items():
        E_ksi = float(props['E'] * MPA2KSI)
        r = sap_model.PropMaterial.SetMaterial(name, 6)
        if r != 0:
            print(f"  ⚠ SetMaterial({name}) failed: ret={r}")
            continue
        r = sap_model.PropMaterial.SetMPIsotropic(name, E_ksi, 0.3, float(1.17e-5))
        if r != 0:
            print(f"  ⚠ SetMPIsotropic({name}) failed: ret={r}")
        defined.append(name)
        print(f"  ✓ {name}: fy={props['fy']} MPa, fu={props['fu']} MPa, E={props['E']} MPa")
    return defined


def define_column_sections(sap_model) -> list:
    defined = []
    for size_mm in COLUMN_SIZES_MM:
        size_in  = float(size_mm * MM2IN)
        cover_in = float((40 + 8) * MM2IN)
        tie_spac = float(0.3 * size_in)
        for grade in CONCRETE_GRADES:
            sec_name = f'C{size_mm}x{size_mm}-{grade}'
            r = sap_model.PropFrame.SetRectangle(sec_name, grade, size_in, size_in)
            if r != 0:
                print(f"  ⚠ SetRectangle({sec_name}) failed: ret={r}")
                continue
            defined.append(sec_name)
    print(f"  ✓ Defined {len(defined)} column sections ({len(COLUMN_SIZES_MM)} sizes x {len(CONCRETE_GRADES)} grades)")
    return defined


def define_beam_sections(sap_model) -> list:
    defined = []
    for b_mm, d_mm in BEAM_SIZES_MM.items():
        b_in     = float(b_mm * MM2IN)
        d_in     = float(d_mm * MM2IN)
        cover_in = float(BEAM_COVER_MM * MM2IN)
        for grade in CONCRETE_GRADES:
            sec_name = f'B{b_mm}x{d_mm}-{grade}'
            r = sap_model.PropFrame.SetRectangle(sec_name, grade, d_in, b_in)
            if r != 0:
                print(f"  ⚠ SetRectangle({sec_name}) failed: ret={r}")
                continue
            defined.append(sec_name)
    print(f"  ✓ Defined {len(defined)} beam sections ({len(BEAM_SIZES_MM)} sizes x {len(CONCRETE_GRADES)} grades)")
    return defined


def delete_old_sections(sap_model) -> None:
    for name in OLD_SECTIONS:
        r = sap_model.PropFrame.Delete(name)
        if r != 0:
            print(f"  ⚠ Could not delete '{name}': ret={r} (may still be assigned)")
        else:
            print(f"  ✓ Deleted old section: {name}")


def reassign_frames(sap_model, frames: list) -> dict:
    beam_count = col_count = fail_count = 0
    for frame in frames:
        target = START_COL_SECTION if frame.obj_type == 'Column' else START_BEAM_SECTION
        r = sap_model.FrameObj.SetSection(frame.unique_name, target, 0)
        if r != 0:
            print(f"  ⚠ SetSection({frame.unique_name} -> {target}) failed: ret={r}")
            fail_count += 1
        else:
            if frame.obj_type == 'Column':
                col_count += 1
            else:
                beam_count += 1
    print(f"  ✓ Reassigned {col_count} columns -> {START_COL_SECTION}")
    print(f"  ✓ Reassigned {beam_count} beams   -> {START_BEAM_SECTION}")
    if fail_count:
        print(f"  ⚠ {fail_count} assignments failed")
    return {'columns': col_count, 'beams': beam_count, 'failures': fail_count}


def verify_sections(sap_model, col_sections: list, beam_sections: list) -> None:
    r = sap_model.PropFrame.GetAllFrameProperties()
    if r[-1] != 0:
        print("  ⚠ Verification: GetAllFrameProperties failed")
        return
    names_in_model = set(r[1])
    missing_cols  = [s for s in col_sections  if s not in names_in_model]
    missing_beams = [s for s in beam_sections if s not in names_in_model]
    still_old     = [s for s in OLD_SECTIONS  if s in names_in_model]
    total = len(col_sections) + len(beam_sections)
    if not missing_cols and not missing_beams:
        print(f"  ✓ All {total} RCC sections confirmed in model")
    else:
        if missing_cols:  print(f"  ⚠ Missing columns: {missing_cols}")
        if missing_beams: print(f"  ⚠ Missing beams:   {missing_beams}")
    if not still_old:
        print("  ✓ All old sections successfully deleted")
    else:
        print(f"  ⚠ Old sections still present: {still_old}")
    print(f"  Total sections now in model: {r[0]}")


def define_rcc_model(sap_model, frames: list) -> dict:
    print("\n── Defining RCC Materials & Sections ──────────────────")

    print("\n[1/6] Defining concrete materials (M20-M45)...")
    conc_mats = define_concrete_materials(sap_model)

    print("\n[2/6] Defining rebar materials (Fe500, Fe415)...")
    rebar_mats = define_rebar_materials(sap_model)

    print("\n[3/6] Defining column sections (30 total)...")
    col_sections = define_column_sections(sap_model)

    print("\n[4/6] Defining beam sections (30 total)...")
    beam_sections = define_beam_sections(sap_model)

    print("\n[5/6] Reassigning all frames to starting RCC sections...")
    assignment = reassign_frames(sap_model, frames)

    print("\n[6/6] Deleting old steel/non-RCC sections...")
    delete_old_sections(sap_model)

    print("\n[Verify] Checking model state...")
    verify_sections(sap_model, col_sections, beam_sections)

    print("\n── RCC Model Definition Complete ───────────────────────\n")

    return {
        'concrete_materials': conc_mats,
        'rebar_materials':    rebar_mats,
        'col_sections':       col_sections,
        'beam_sections':      beam_sections,
        'assignment':         assignment,
    }


if __name__ == "__main__":
    from connect_etabs import attach_to_running_etabs, unlock_model
    from read_model import read_frame_objects

    etabs_obj, sap_model = attach_to_running_etabs()
    unlock_model(sap_model)

    print("Reading frame objects from model...")
    frames = read_frame_objects(sap_model)
    print(f"  {len(frames)} frames loaded "
          f"({sum(1 for f in frames if f.obj_type=='Column')} columns, "
          f"{sum(1 for f in frames if f.obj_type=='Beam')} beams)")

    result = define_rcc_model(sap_model, frames)

    r = sap_model.File.Save()
    if r == 0:
        print("✓ Model saved.")
    else:
        print(f"⚠ Save failed: ret={r}")

    print("\nSummary:")
    print(f"  Concrete materials : {result['concrete_materials']}")
    print(f"  Rebar materials    : {result['rebar_materials']}")
    print(f"  Column sections    : {len(result['col_sections'])} defined")
    print(f"  Beam sections      : {len(result['beam_sections'])} defined")
    print(f"  Frame assignments  : {result['assignment']}")