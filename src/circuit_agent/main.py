from __future__ import annotations
import argparse,json,shutil
from pathlib import Path
from .domain import ApprovalRequired
from .api import serve
from .orchestrator import Orchestrator
from .storage import ProjectStore
from .validation import validate_circuit_ir,validate_requirements

def runtime(args): return ProjectStore(Path(args.database),Path(args.artifacts))
def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="circuit-agent",description="Low-voltage educational circuit workflow")
    parser.add_argument("--database",default="data/circuit_agent.db"); parser.add_argument("--artifacts",default="runs")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("validate","create"): sub.add_parser(name).add_argument("spec")
    for name in ("run","status","resume","cancel"): sub.add_parser(name).add_argument("project_id")
    ap=sub.add_parser("approve"); ap.add_argument("project_id"); ap.add_argument("--subject",required=True,choices=["design","optimization"]); ap.add_argument("--revision",required=True,type=int); ap.add_argument("--comment",default="")
    ep=sub.add_parser("export"); ep.add_argument("project_id"); ep.add_argument("--out",required=True)
    server=sub.add_parser("serve",help="Run the local JSON API"); server.add_argument("--host",default="127.0.0.1"); server.add_argument("--port",type=int,default=8000)
    args=parser.parse_args(argv)
    if args.command in {"validate","create"}:
        spec=json.loads(Path(args.spec).read_text()); errors=validate_requirements(spec)+validate_circuit_ir(spec.get("circuit_ir",{}))
        if args.command=="validate": print(json.dumps({"valid":not errors,"errors":errors},indent=2)); return 0 if not errors else 2
        if errors: print(json.dumps({"valid":False,"errors":errors},indent=2)); return 2
        store=runtime(args); pid=store.create_project(spec); print(pid); return 0
    store=runtime(args)
    if args.command=="serve": serve(store,args.host,args.port); return 0
    orchestrator=Orchestrator(store)
    if args.command=="status": print(json.dumps(store.project(args.project_id),indent=2)); return 0
    if args.command=="run": print(json.dumps(orchestrator.run(args.project_id),indent=2)); return 0
    if args.command=="approve": store.approve(args.project_id,args.subject,str(args.revision),comment=args.comment); print("approval recorded"); return 0
    if args.command=="resume":
        try: print(json.dumps(orchestrator.resume(args.project_id),indent=2)); return 0
        except ApprovalRequired as exc: print(f"approval required: {exc}"); return 3
    if args.command=="cancel": store.cancel(args.project_id); print("cancelled"); return 0
    if args.command=="export":
        target=Path(args.out); target.mkdir(parents=True,exist_ok=True)
        for artifact in store.artifacts(args.project_id): shutil.copy2(artifact["storage_path"],target/Path(artifact["storage_path"]).name)
        print(target); return 0
    return 1
if __name__=="__main__": raise SystemExit(main())
