import argparse,json
from pathlib import Path
from circuit_agent.tools import generate_spice_netlist
def main():
    p=argparse.ArgumentParser(); p.add_argument("spec"); p.add_argument("--out",required=True); a=p.parse_args()
    spec=json.loads(Path(a.spec).read_text()); Path(a.out).write_text(generate_spice_netlist(spec["circuit_ir"])); print(a.out)
if __name__=="__main__": main()
