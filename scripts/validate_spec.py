import argparse,json
from pathlib import Path
from circuit_agent.validation import validate_circuit_ir,validate_requirements
def main():
    p=argparse.ArgumentParser();p.add_argument("spec");a=p.parse_args(); d=json.loads(Path(a.spec).read_text()); errors=validate_requirements(d)+validate_circuit_ir(d.get("circuit_ir",{})); print("VALIDATION PASSED" if not errors else "VALIDATION FAILED\n"+"\n".join(errors)); return bool(errors)
if __name__=="__main__": raise SystemExit(main())
