import streamlit as st
from collections import defaultdict
import pandas as pd
import math
import io

###############################################################################
# SHARED UTILITIES
###############################################################################

def calc_dispense_portion(disp_vol: float, double_disp: bool) -> float:
    return disp_vol * (2 if double_disp else 1)

def check_volume_warning(volume: float) -> str:
    if volume > 6000:
        return "EXCEEDS 6000 µL limit!"
    if volume > 4000:
        return "Consider splitting!"
    return ""

def format_number(num: float) -> str:
    if float(num).is_integer():
        return str(int(num))
    return f"{num:.4g}"

def choose_diluent(rtype: str, reagent_name: str="", custom: str="") -> str:
    if rtype in ["H2O2", "PB", "Polymer", "Vectaplex"]:
        return ""
    if rtype == "Opal":
        return "bondwash/blocker" if "780" in reagent_name else "amplifier"
    if rtype == "TSA-DIG":
        return "amplifier"
    if rtype == "Primary":
        return "bondwash/blocker"
    if rtype == "DAPI":
        return "TBS"
    if rtype == "Custom":
        return custom
    return ""

def split_row(row: dict, max_allowed=5000, dead_vol=150) -> list[dict]:
    try:
        total_vol = float(row["Total Volume (µL)"])
    except:
        return [row]
    if total_vol <= max_allowed:
        return [row]

    base = row.get("__base_portion", total_vol - dead_vol)
    max_portion = max_allowed - dead_vol
    if max_portion <= 0:
        return [row]

    needed = math.ceil(base / max_portion)
    leftover = base
    try:
        dil = float(row["Dilution Factor"])
    except:
        dil = 1.0

    out = []
    for i in range(needed):
        portion = min(leftover, max_portion)
        leftover -= portion
        tv = dead_vol + portion
        sv = tv / dil

        new = row.copy()
        new["Reagent"] += f" (Split {i+1}/{needed})"
        new["Total Volume (µL)"]   = format_number(tv)
        new["Stock Volume (µL)"]   = format_number(sv)
        new["Diluent Volume (µL)"] = format_number(tv - sv)
        new["Warning"]             = check_volume_warning(tv)
        out.append(new)
    return out

TYPE_ORDER = ["H2O2","PB","Primary","Polymer","TSA-DIG","Opal","DAPI","Vectaplex","Custom"]
type_rank  = {t:i for i,t in enumerate(TYPE_ORDER)}

###############################################################################
# SINGLE-PLEX FLOW
###############################################################################

def single_plex_flow(dispense_vol: float, dead_vol: float):
    st.write("### Single-Plex Flow")

    # ── session-state init ─────────────────────────────────────────────────────
    st.session_state.setdefault("sp_slides", [])
    st.session_state.setdefault("sp_final_rows", [])
    st.session_state.setdefault("sp_computed", False)
    st.session_state.setdefault("sp_pot_named", False)
    st.session_state.setdefault("sp_pot_names", {})
    st.session_state.setdefault("sp_split_done", False)

    # ── 1) Add Slide UI ────────────────────────────────────────────────────────
    st.subheader("Add Single-Plex Slide")
    sp_h2o2 = st.checkbox("Use H2O2?", True)
    sp_pb   = st.checkbox("Use Protein Block?", True)
    sp_neg  = st.checkbox("Negative Control? (skip primary)", False)

    sp_name = st.text_input("Primary Name")
    sp_dil  = st.number_input("Primary Dilution Fold", 1.0, 1000.0)
    sp_dbl  = st.checkbox("2× Primary?", False)

    sp_poly  = st.selectbox("Polymer", ["Rabbit","Sheep","Goat","Mouse","Rat","Others"])
    sp_poldb= st.checkbox("2× Polymer?", False)

    sp_opal = st.selectbox("Opal", ["480","520","540","570","620","650","690","780","others"])
    sp_opdil= st.number_input("Opal Dilution Fold", 1.0, 1000.0)
    sp_opdb = st.checkbox("2× Opal?", False)

    sp_tsa=False; sp_tsd=1000.0; sp_tsb=False
    if sp_opal=="780":
        sp_tsa = st.checkbox("Use TSA-DIG?")
        if sp_tsa:
            sp_tsd = st.number_input("TSA-DIG Dilution Fold", 1.0, 1000.0)
            sp_tsb = st.checkbox("2× TSA?", False)

    sp_dapi=False; sp_ddl=1000.0; sp_ddb=False
    if st.checkbox("Use DAPI?", False):
        sp_dapi= True
        sp_ddl = st.number_input("DAPI Dilution Fold", 1.0, 1000.0)
        sp_ddb = st.checkbox("2× DAPI?", False)

    sp_usec=False; sp_cname=""; sp_cdl=1.0; sp_cdb=False; sp_cil=""
    if st.checkbox("Use Custom Reagent?", False):
        sp_usec = True
        sp_cname= st.text_input("Custom Name")
        sp_cdl  = st.number_input("Custom Dilution Fold", 1.0, 1000.0)
        sp_cdb  = st.checkbox("2× Custom?", False)
        sp_cil  = st.text_input("Custom Diluent", "bondwash/blocker")

    if st.button("Add Slide"):
        if not sp_neg and not sp_name.strip():
            st.warning("Provide a primary name or check Negative Control.")
        elif sp_usec and not sp_cname.strip():
            st.warning("Provide a custom name or uncheck Custom.")
        else:
            st.session_state["sp_slides"].append({
                "H2O2": sp_h2o2, "PB": sp_pb, "Neg": sp_neg,
                "Primary": (sp_name.strip(), sp_dil, sp_dbl),
                "Polymer": (sp_poly, sp_poldb),
                "Opal":    (sp_opal, sp_opdil, sp_opdb),
                "TSA":     (sp_tsa, sp_tsd, sp_tsb),
                "DAPI":    (sp_dapi, sp_ddl, sp_ddb),
                "Custom":  (sp_usec, sp_cname.strip(), sp_cdl, sp_cdb, sp_cil.strip())
            })
            st.success("Slide added.")

    # ── 2) Remove Slides ───────────────────────────────────────────────────────
    st.write("#### Current Slides")
    for i, sl in enumerate(st.session_state["sp_slides"]):
        c1, c2 = st.columns([4,1])
        with c1:
            st.write(f"#{i+1}: Prim={sl['Primary'][0]}, Opal={sl['Opal'][0]}, Neg={sl['Neg']}")
        with c2:
            if st.button(f"Remove {i+1}", key=f"rem_sp_{i}"):
                st.session_state["sp_slides"].pop(i)
                st.experimental_rerun()

    # ── 3) Build Usage Logic ──────────────────────────────────────────────────
    def build_sp_table():
        um, summary = defaultdict(list), []
        for idx, sl in enumerate(st.session_state["sp_slides"], start=1):
            seq=[]
            if sl["H2O2"]:
                um[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False)); seq.append("H2O2")
            if sl["PB"]:
                um[("PB","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False)); seq.append("PB")

            # primary
            nm, dil, dbl = sl["Primary"]
            if not sl["Neg"]:
                um[(nm,"Primary",dil,dbl,"")].append(calc_dispense_portion(dispense_vol,dbl))
                seq.append(f"Primary({nm})")
            else:
                seq.append("Primary(skipped)")

            # polymer
            pol, pdb = sl["Polymer"]
            key = f"Polymer-{pol}"
            um[(key,"Polymer",1.0,pdb,"")].append(calc_dispense_portion(dispense_vol,pdb)); seq.append(key)

            # opal
            op, odl, odb = sl["Opal"]
            on = f"Opal-{op}"
            um[(on,"Opal",odl,odb,"")].append(calc_dispense_portion(dispense_vol,odb)); seq.append(on)

            # TSA
            tsa, tsd, tsb = sl["TSA"]
            if tsa:
                um[("TSA-DIG","TSA-DIG",tsd,tsb,"")].append(calc_dispense_portion(dispense_vol,tsb)); seq.append("TSA-DIG")

            # DAPI
            dapi, ddl, ddb = sl["DAPI"]
            if dapi:
                um[("DAPI","DAPI",ddl,ddb,"")].append(calc_dispense_portion(dispense_vol,ddb)); seq.append("DAPI")

            # custom
            usec, cn, cdl, cdb, cil = sl["Custom"]
            if usec:
                um[(cn,"Custom",cdl,cdb,cil)].append(calc_dispense_portion(dispense_vol,cdb)); seq.append(f"Custom({cn})")

            summary.append({"Slide":idx, "Sequence":" → ".join(seq)})

        st.subheader("Slide Summary")
        st.table(summary)

        out=[]
        for (name, rtype, dil, dbl, cdi), pts in um.items():
            s = sum(pts)
            tv = dead_vol + s
            sv = tv / dil
            wr = check_volume_warning(tv)
            dilu = cdi if rtype=="Custom" else choose_diluent(rtype,name,cdi)
            out.append({
                "Reagent": name,
                "Type":    rtype,
                "Dilution Factor": format_number(dil),
                "Double Disp?":    "Yes" if dbl else "No",
                "Diluent":         dilu,
                "Total Volume (µL)":   format_number(tv),
                "Stock Volume (µL)":   format_number(sv),
                "Diluent Volume (µL)": format_number(tv-sv),
                "Warning":         wr,
                "__base_portion":  s
            })
        st.session_state["sp_final_rows"] = out
        st.session_state["sp_split_done"]  = False

    # ── 4) Compute Button ──────────────────────────────────────────────────────
    if st.button("Compute Single-Plex Table"):
        build_sp_table()
        st.session_state["sp_computed"]  = True
        st.session_state["sp_pot_named"] = False
        st.success("Computed—now name your pots.")

    # ── 5) Pot Naming ──────────────────────────────────────────────────────────
    final = st.session_state.get("sp_final_rows", [])
    if st.session_state["sp_computed"] and final and not st.session_state["sp_pot_named"]:
        st.subheader("Name Your Pots")
        with st.form("sp_pot_form"):
            if not st.session_state["sp_pot_names"]:
                st.session_state["sp_pot_names"] = {r["Reagent"]: r["Reagent"] for r in final}
            for reagent in st.session_state["sp_pot_names"]:
                key = f"sp_pot_{reagent}"
                st.session_state["sp_pot_names"][reagent] = st.text_input(
                    label=reagent,
                    value=st.session_state["sp_pot_names"][reagent],
                    key=key
                )
            if st.form_submit_button("Save Pot Names"):
                st.session_state["sp_pot_named"] = True
                st.success("Pot names saved—scroll down for your table.")

    # ── 6) Splitting Prompt ────────────────────────────────────────────────────
    rows = st.session_state.get("sp_final_rows", [])
    needs = any(r["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"] for r in rows)
    if st.session_state["sp_pot_named"] and needs and not st.session_state["sp_split_done"]:
        if st.button("Split Rows >4000 µL?"):
            new = []
            for r in rows:
                if r["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"]:
                    new.extend(split_row(r, max_allowed=4000, dead_vol=dead_vol))
                else:
                    new.append(r)
            st.session_state["sp_final_rows"] = new
            st.session_state["sp_split_done"]  = True
            st.success("Splitting done—see updated table.")

    # ── 7) Final Table & Exports ───────────────────────────────────────────────
    if st.session_state["sp_pot_named"]:
        df = pd.DataFrame(st.session_state["sp_final_rows"]).drop(columns=["__base_portion"], errors="ignore")

        # Pot Name column
        pn = st.session_state["sp_pot_names"]
        df.insert(0, "Pot Name", df["Reagent"].map(pn))

        # Sort by Type then Pot Name
        df["__rk"] = df["Type"].map(lambda x: type_rank.get(x, 9999))
        df.sort_values(by=["__rk","Pot Name"], inplace=True)
        df.drop(columns="__rk", inplace=True)

        # Highlight
        def hl(r):
            v = float(r["Total Volume (µL)"])
            if v>6000: return ["background-color:#ffcccc"]*len(r)
            if v>4000: return ["background-color:#ffffcc"]*len(r)
            return [""]*len(r)

        st.subheader("Final Single-Plex Table")
        st.write(df.style.apply(hl, axis=1).to_html(), unsafe_allow_html=True)

        if len(df)>29:
            st.error(f"{len(df)} pots—exceeds 29-pot limit!")

        # Download & Print
        st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), "single_v1.1.csv", "text/csv")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="SinglePlex")
        st.download_button("⬇️ Download Excel", buf.getvalue(),
                           "single_v1.1.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("<button onclick='window.print()'>🖨 Print Table</button>", unsafe_allow_html=True)

        # Sequence Guide
        st.subheader("Sequence Guide")
        st.write("Slide 1: " + " → ".join(df["Pot Name"]))

###############################################################################
# MULTI-PLEX FLOW
###############################################################################

def multi_plex_flow(dispense_vol: float, dead_vol: float):
    st.write("### Multi-Plex Flow")

    # ── init state ─────────────────────────────────────────────────────────────
    st.session_state.setdefault("mp_slides", [])
    st.session_state.setdefault("mp_final_rows_unsplit", [])
    st.session_state.setdefault("mp_final_rows", [])
    st.session_state.setdefault("mp_pot_names", {})
    st.session_state.setdefault("mp_pot_named", False)
    st.session_state.setdefault("mp_split_done", False)

    # ── 1) Add Slide UI ────────────────────────────────────────────────────────
    st.subheader("Add Multi-Plex Slide")
    mp_h2o2      = st.checkbox("Use H2O2?", True)
    mp_pb_before = st.checkbox("Use PB before primary?", True)
    mp_pb_after  = st.checkbox("Use PB after opal?", False)
    mp_neg       = st.checkbox("Negative Control? (skip all primary)", False)

    mp_use_dapi=False; mp_dd=1000.0; mp_db=False
    if st.checkbox("Use DAPI?", False):
        mp_use_dapi=True
        mp_dd  = st.number_input("DAPI Dilution Fold",1.0,1000.0)
        mp_db  = st.checkbox("2× DAPI?", False)

    mp_use_cust=False; mp_cn=""; mp_cd=1.0; mp_cb=False; mp_ci=""
    if st.checkbox("Use Custom Reagent?", False):
        mp_use_cust=True
        mp_cn=st.text_input("Custom Name")
        mp_cd=st.number_input("Custom Dilution Fold",1.0,1000.0)
        mp_cb=st.checkbox("2× Custom?", False)
        mp_ci=st.text_input("Custom Diluent","bondwash/blocker")

    mp_vect=False; mp_vdb=False
    if st.checkbox("Use Vectaplex?", False):
        mp_vect=True
        mp_vdb=st.checkbox("2× Vectaplex?", False)

    mp_n = st.number_input("Number of plexes",1,8,2)

    used_opals=set(); warn_pos=False; warn_dup=False
    plex_list=[]
    st.write("#### Configure Each Plex")
    for i in range(mp_n):
        st.markdown(f"**Plex {i+1}**")
        c1,c2,c3 = st.columns([2,1,1])
        with c1:
            name = st.text_input(f"Primary (#{i+1})", key=f"mp_pn_{i}")
        with c2:
            pdil = st.number_input(f"Prim Dil (#{i+1})",1.0,1000.0, key=f"mp_pd_{i}")
        with c3:
            pdb  = st.checkbox("2× Primary?", False, key=f"mp_pdb_{i}")

        c4,c5=st.columns([2,1])
        with c4:
            poly = st.selectbox(f"Polymer (#{i+1})",["Rabbit","Sheep","Goat","Mouse","Rat","Others"], key=f"mp_poly_{i}")
        with c5:
            pdb2 = st.checkbox("2× Polymer?", False, key=f"mp_pdb2_{i}")

        c6,c7,c8=st.columns([2,1,1])
        with c6:
            opal=st.selectbox(f"Opal (#{i+1})",["480","520","540","570","620","650","690","780","others"], key=f"mp_opal_{i}")
        with c7:
            odil=st.number_input(f"Opal Dil (#{i+1})",1.0,1000.0, key=f"mp_odil_{i}")
        with c8:
            odb = st.checkbox("2× Opal?", False, key=f"mp_odb_{i}")

        if opal not in ["others","780"] and opal in used_opals:
            warn_dup=True
        used_opals.add(opal)
        if opal=="780" and i<mp_n-1:
            warn_pos=True

        tsa=False; tsd=1000.0; tsb=False
        if opal=="780":
            tsa = st.checkbox(f"Use TSA-DIG? (#{i+1})", key=f"mp_tsa_{i}")
            if tsa:
                tsd = st.number_input(f"TSA Dil (#{i+1})",1.0,1000.0, key=f"mp_tsd_{i}")
                tsb = st.checkbox("2× TSA?", False, key=f"mp_tsb_{i}")

        plex_list.append({
            "primary_name": name.strip(),
            "primary_dil": pdil,
            "primary_dbl": pdb,
            "polymer": poly,
            "polymer_dbl": pdb2,
            "opal": opal,
            "opal_dil": odil,
            "opal_dbl": odb,
            "tsa_used": tsa,
            "tsa_dil": tsd,
            "tsa_dbl": tsb
        })

    if st.button("Add Multi-Plex Slide"):
        if warn_pos:
            st.error("Opal 780 must be last plex.")
        elif warn_dup:
            st.error("Duplicate non-780 Opal.")
        elif mp_use_cust and not mp_cn.strip():
            st.warning("Enter custom name or uncheck Custom.")
        else:
            st.session_state["mp_slides"].append({
                "h2o2": mp_h2o2,
                "pb_before": mp_pb_before,
                "pb_after": mp_pb_after,
                "neg": mp_neg,
                "use_dapi": mp_use_dapi, "dapi_dil": mp_dd, "dapi_dbl": mp_db,
                "use_custom": mp_use_cust, "cust_name": mp_cn.strip(), "cust_dil": mp_cd, "cust_dbl": mp_cb, "cust_dilu": mp_ci.strip(),
                "vectaplex": mp_vect,   "vectaplex_dbl": mp_vdb,
                "plex_list": plex_list
            })
            st.success("Multi-Plex slide added.")

    # ── remove slides ──────────────────────────────────────────────────────────
    st.write("#### Current Multi-Plex Slides")
    for i, sl in enumerate(st.session_state["mp_slides"]):
        c1,c2=st.columns([4,1])
        with c1:
            st.write(f"#{i+1}: plex={len(sl['plex_list'])}, vec={sl['vectaplex']}")
        with c2:
            if st.button(f"Remove {i+1}", key=f"rem_mp_{i}"):
                st.session_state["mp_slides"].pop(i)
                st.experimental_rerun()

    # ── build usage ────────────────────────────────────────────────────────────
    def build_mp_table():
        um, summary = defaultdict(list), []
        for idx, sl in enumerate(st.session_state["mp_slides"], start=1):
            seq=[]
            if sl["h2o2"]:
                um[("H2O2","H2O2",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False)); seq.append("H2O2")
            for i, px in enumerate(sl["plex_list"], start=1):
                if sl["pb_before"]:
                    um[("PB","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False)); seq.append("PB(before)")
                nm = px["primary_name"] or f"P{i}"
                if not sl["neg"]:
                    um[(nm,"Primary",px["primary_dil"],px["primary_dbl"],"")].append(
                        calc_dispense_portion(dispense_vol,px["primary_dbl"])
                    )
                seq.append(f"Primary({nm})")
                poly = f"Polymer-{px['polymer']}"
                um[(poly,"Polymer",1.0,px["polymer_dbl"],"")].append(
                    calc_dispense_portion(dispense_vol,px["polymer_dbl"])
                )
                seq.append(poly)

                if px["opal"]=="780":
                    if px["tsa_used"]:
                        um[("TSA-DIG","TSA-DIG",px["tsa_dil"],px["tsa_dbl"],"")].append(
                            calc_dispense_portion(dispense_vol,px["tsa_dbl"])
                        )
                        seq.append("TSA-DIG")
                    if sl["vectaplex"]:
                        p = calc_dispense_portion(dispense_vol,sl["vectaplex_dbl"])
                        um[("Vectaplex A","Vectaplex",1.0,False,"")].append(p)
                        um[("Vectaplex B","Vectaplex",1.0,False,"")].append(p)
                        seq.append("Vectaplex(A+B)")
                    op_name = "Opal-780"
                else:
                    op_name = f"Opal-{px['opal']}"
                um[(op_name,"Opal",px["opal_dil"],px["opal_dbl"],"")].append(
                    calc_dispense_portion(dispense_vol,px["opal_dbl"])
                )
                seq.append(op_name)
                if sl["vectaplex"] and px["opal"]!="780":
                    p = calc_dispense_portion(dispense_vol,sl["vectaplex_dbl"])
                    um[("Vectaplex A","Vectaplex",1.0,False,"")].append(p)
                    um[("Vectaplex B","Vectaplex",1.0,False,"")].append(p)
                    seq.append("Vectaplex(A+B)")
                if sl["pb_after"]:
                    um[("PB","PB",1.0,False,"")].append(calc_dispense_portion(dispense_vol,False)); seq.append("PB(after)")

            if sl["use_dapi"]:
                um[("DAPI","DAPI",sl["dapi_dil"],sl["dapi_dbl"],"")].append(
                    calc_dispense_portion(dispense_vol,sl["dapi_dbl"])
                )
                seq.append("DAPI")
            if sl["use_custom"]:
                cn,cd,cb,ci = sl["cust_name"], sl["cust_dil"], sl["cust_dbl"], sl["cust_dilu"]
                um[(cn,"Custom",cd,cb,ci)].append(
                    calc_dispense_portion(dispense_vol,cb)
                )
                seq.append(f"Custom({cn})")

            summary.append({"Slide":idx, "Sequence":" → ".join(seq)})

        st.subheader("Multi-Plex Slide Summary")
        st.table(summary)

        out=[]
        for (name,rtype,dil,dbl,cdi), pts in um.items():
            s=sum(pts); tv=dead_vol+s; sv=tv/dil; wr=check_volume_warning(tv)
            dilu = cdi if rtype=="Custom" else choose_diluent(rtype,name,cdi)
            out.append({
                "Reagent":name,
                "Type":rtype,
                "Dilution Factor":format_number(dil),
                "Double Disp?":"Yes" if dbl else "No",
                "Diluent":dilu,
                "Total Volume (µL)":format_number(tv),
                "Stock Volume (µL)":format_number(sv),
                "Diluent Volume (µL)":format_number(tv-sv),
                "Warning":wr,
                "__base_portion":s
            })

        st.session_state["mp_final_rows_unsplit"] = out
        st.session_state["mp_split_done"]     = False
        st.session_state["mp_final_rows"]     = out

    # ── Compute Button ─────────────────────────────────────────────────────────
    if st.button("Compute Multi-Plex Table"):
        build_mp_table()
        st.session_state["mp_pot_named"] = False
        st.success("Computed—now name your pots.")

    # ── Pot Naming ─────────────────────────────────────────────────────────────
    final = st.session_state.get("mp_final_rows", [])
    if final and not st.session_state["mp_pot_named"]:
        st.subheader("Name Your Pots")
        with st.form("mp_pot_form"):
            if not st.session_state["mp_pot_names"]:
                st.session_state["mp_pot_names"] = {r["Reagent"]:r["Reagent"] for r in final}
            for reagent in st.session_state["mp_pot_names"]:
                key = f"mp_pot_{reagent}"
                st.session_state["mp_pot_names"][reagent] = st.text_input(
                    label=reagent,
                    value=st.session_state["mp_pot_names"][reagent],
                    key=key
                )
            if st.form_submit_button("Save Pot Names"):
                st.session_state["mp_pot_named"] = True
                st.success("Pot names saved—scroll down for your table.")

    # ── Splitting Prompt ───────────────────────────────────────────────────────
    rows = st.session_state.get("mp_final_rows", [])
    needs=any(r["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"] for r in rows)
    if st.session_state["mp_pot_named"] and needs and not st.session_state["mp_split_done"]:
        if st.button("Split Rows >4000 µL?"):
            new=[]
            for r in rows:
                if r["Warning"] in ["Consider splitting!","EXCEEDS 6000 µL limit!"]:
                    new.extend(split_row(r, max_allowed=4000, dead_vol=dead_vol))
                else:
                    new.append(r)
            st.session_state["mp_final_rows"]=new
            st.session_state["mp_split_done"]=True
            st.success("Splitting done—see updated table.")

    # ── Final Table & Exports ─────────────────────────────────────────────────
    if st.session_state["mp_pot_named"]:
        df = pd.DataFrame(st.session_state["mp_final_rows"]).drop(columns=["__base_portion"], errors="ignore")
        pn = st.session_state["mp_pot_names"]
        df.insert(0, "Pot Name", df["Reagent"].map(lambda r: pn.get(r, pn.get(r.split(" (")[0],r.split(" (")[0]))))
        df["__rk"]=df["Type"].map(lambda x:type_rank.get(x,9999))
        df.sort_values(by=["__rk","Pot Name"], inplace=True); df.drop("__rk",axis=1,inplace=True)

        def hl(r):
            v=float(r["Total Volume (µL)"])
            if v>6000: return ["background-color:#ffcccc"]*len(r)
            if v>4000: return ["background-color:#ffffcc"]*len(r)
            return [""]*len(r)

        st.subheader("Multi-Plex Reagent Table")
        st.write(df.style.apply(hl, axis=1).to_html(), unsafe_allow_html=True)
        if len(df)>29:
            st.error(f"{len(df)} pots exceed 29-pot limit!")

        st.download_button("⬇️ CSV", df.to_csv(index=False).encode(), "multi_v1.1.csv", "text/csv")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as w:
            df.to_excel(w,index=False,sheet_name="MultiPlex")
        st.download_button("⬇️ Excel", buf.getvalue(),
                           "multi_v1.1.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("<button onclick='window.print()'>🖨 Print Table</button>", unsafe_allow_html=True)

        st.subheader("Plex Sequence Guide")
        guide=[]
        for si, sl in enumerate(st.session_state["mp_slides"], start=1):
            parts=[]
            for px in sl["plex_list"]:
                base=px["primary_name"] or ""
                parts.append(pn.get(base,base))
                parts.append(pn.get(f"Polymer-{px['polymer']}",f"Polymer-{px['polymer']}"))
                parts.append(pn.get(f"Opal-{px['opal']}",f"Opal-{px['opal']}"))
            guide.append({"Slide":si, "Sequence":" → ".join(parts)})
        st.table(pd.DataFrame(guide))

###############################################################################
# MAIN APP
###############################################################################

def main_app():
    st.title("BondRX Opal Reagent Prep Bot v1.1")
    dispense_vol = st.number_input("Dispense Volume (µL)", 1, 9999, 150)
    dead_vol     = st.number_input("Dead Volume (µL)", 0, 9999, 150)
    st.write("---")

    choice = st.radio("Select Flow:", ["Single-Plex","Multi-Plex"])
    if choice=="Single-Plex":
        single_plex_flow(dispense_vol, dead_vol)
    else:
        multi_plex_flow(dispense_vol, dead_vol)

if __name__=="__main__":
    main_app()
