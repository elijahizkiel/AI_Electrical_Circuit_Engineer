from __future__ import annotations
import csv, math, re
from pathlib import Path
from .validation import require_valid_ir

def spice_value(value: float) -> str: return f"{value:g}"
def generate_spice_netlist(ir: dict) -> str:
    require_valid_ir(ir); lines=[f"* {ir['title']}", "* Generated from canonical CircuitIR"]
    for c in ir["components"]:
        p=c["parameters"]; pins=c["pins"]
        if c["kind"]=="resistor": lines.append(f"{c['ref']} {pins['1']} {pins['2']} {spice_value(p['resistance_ohm'])}")
        elif c["kind"]=="capacitor": lines.append(f"{c['ref']} {pins['1']} {pins['2']} {spice_value(p['capacitance_farad'])}")
        else: lines.append(f"{c['ref']} {pins['positive']} {pins['negative']} DC {spice_value(p['dc_voltage_v'])}")
    for a in ir["analyses"]:
        if a["kind"]=="op": lines.append(".op")
        elif a["kind"]=="transient": lines.append(f".tran {a['max_step_s']:g} {a['stop_time_s']:g}")
        elif a["kind"]=="ac": lines.append(f".ac dec {a.get('points_per_decade',100)} {a['start_frequency_hz']:g} {a['stop_frequency_hz']:g}")
    return "\n".join(lines+[".end",""])
def generate_ltspice_asc(ir:dict)->str:
    require_valid_ir(ir); symbols={"resistor":"res","capacitor":"cap","voltage_source":"voltage"}; lines=["Version 4","SHEET 1 1200 800"]
    for i,c in enumerate(ir["components"]):
        x,y=160+i*160,160; val=next(iter(c["parameters"].values())); lines += [f"SYMBOL {symbols[c['kind']]} {x} {y} R0",f"SYMATTR InstName {c['ref']}",f"SYMATTR Value {val:g}"]
    lines.append("TEXT 32 32 Left 2 !* Connectivity must be opened and checked in LTspice."); return "\n".join(lines)+"\n"
def parse_log(path:Path)->tuple[list[dict],list[str]]:
    text=path.read_text(errors="replace"); measurements=[]
    for line in text.splitlines():
        m=re.match(r"\s*([A-Za-z][\w.-]*)\s*[:=]\s*([-+0-9.eE]+)",line)
        if m: measurements.append({"id":m.group(1),"value":float(m.group(2)),"unit":"unknown","signal":"log","extraction_method":"log_regex","sample_count":None})
    return measurements,[line.strip() for line in text.splitlines() if re.search(r"warning|error|singular|timestep",line,re.I)]
def analyze_csv(path:Path, metric_defs:list[dict])->list[dict]:
    with path.open(newline="",encoding="utf-8-sig") as fh: rows=list(csv.DictReader(fh))
    if not rows: raise ValueError("CSV has no rows")
    results=[]
    for definition in metric_defs:
        column=definition["signal"]; values=[]
        for row in rows:
            try: values.append(float(row[column]))
            except (KeyError,ValueError,TypeError): pass
        if not values: continue
        kind=definition["kind"]; val={"min":min(values),"max":max(values),"peak":max(values),"peak_to_peak":max(values)-min(values),"mean":sum(values)/len(values),"rms":math.sqrt(sum(v*v for v in values)/len(values))}.get(kind)
        if val is not None: results.append({"id":definition["id"],"value":val,"unit":definition["unit"],"signal":column,"extraction_method":f"csv_{kind}","sample_count":len(values)})
    return results
