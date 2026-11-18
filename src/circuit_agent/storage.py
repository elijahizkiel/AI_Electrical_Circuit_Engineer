from __future__ import annotations

import hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .domain import ALLOWED_TRANSITIONS, State

def utcnow() -> str: return datetime.now(timezone.utc).isoformat()
def canonical(value: Any) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

class ProjectStore:
    def __init__(self, database_path: Path, artifact_root: Path):
        self.database_path, self.artifact_root = database_path, artifact_root
        database_path.parent.mkdir(parents=True, exist_ok=True); artifact_root.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(database_path); self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON"); self._migrate()
    def _migrate(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,request_text TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,config_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),agent_name TEXT NOT NULL,task_type TEXT NOT NULL,status TEXT NOT NULL,attempt INTEGER NOT NULL,started_at TEXT,finished_at TEXT,input_artifact_id TEXT,output_artifact_id TEXT,error_json TEXT);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),artifact_type TEXT NOT NULL,schema_version TEXT NOT NULL,revision INTEGER NOT NULL,created_by TEXT NOT NULL,storage_path TEXT NOT NULL,content_hash TEXT NOT NULL,parent_ids_json TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS simulation_runs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),design_artifact_id TEXT,adapter TEXT NOT NULL,simulator_version TEXT,status TEXT NOT NULL,started_at TEXT,finished_at TEXT,exit_code INTEGER,result_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS measurements(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),simulation_run_id TEXT,measurement_key TEXT NOT NULL,value REAL,unit TEXT,source_artifact_id TEXT,metadata_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,decision TEXT NOT NULL,comment TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),event_type TEXT NOT NULL,actor TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_artifacts_project_type ON artifacts(project_id,artifact_type); CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id,created_at);
        """); self.conn.commit()
    def create_project(self, spec: dict) -> str:
        pid, now = str(uuid.uuid4()), utcnow(); name = spec.get("name", "Untitled circuit project")
        self.conn.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?)", (pid,name,spec.get("request",spec.get("description",name)),State.CREATED,now,now,canonical(spec))); self.event(pid,"project_created","system",{"name":name}); self.conn.commit(); return pid
    def project(self, pid: str) -> dict:
        row=self.conn.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
        if not row: raise KeyError(f"project not found: {pid}")
        result=dict(row); result["config"]=json.loads(result.pop("config_json")); return result
    def transition(self,pid:str,to:State,actor="orchestrator") -> None:
        project=self.project(pid); current=State(project["status"])
        if to not in ALLOWED_TRANSITIONS.get(current,set()): raise ValueError(f"illegal transition {current} -> {to}")
        now=utcnow(); self.conn.execute("UPDATE projects SET status=?,updated_at=? WHERE id=?",(to,now,pid)); self.event(pid,"state_transition",actor,{"from":current,"to":to}); self.conn.commit()
    def event(self,pid:str,event_type:str,actor:str,payload:dict) -> None:
        self.conn.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),pid,event_type,actor,canonical(payload),utcnow()))
    def task(self,pid:str,agent:str,task_type:str,action) -> Any:
        tid=str(uuid.uuid4()); started=utcnow(); self.conn.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)",(tid,pid,agent,task_type,"running",1,started,None,None,None,None)); self.conn.commit()
        try:
            value=action(tid); self.conn.execute("UPDATE tasks SET status='completed',finished_at=? WHERE id=?",(utcnow(),tid)); self.event(pid,"agent_task_completed",agent,{"task_id":tid,"task_type":task_type}); self.conn.commit(); return value
        except Exception as exc:
            self.conn.execute("UPDATE tasks SET status='failed',finished_at=?,error_json=? WHERE id=?",(utcnow(),canonical({"type":type(exc).__name__,"message":str(exc)}),tid)); self.event(pid,"agent_task_failed",agent,{"task_id":tid,"error":type(exc).__name__}); self.conn.commit(); raise
    def artifact(self,pid:str,kind:str,content:dict,created_by:str,parent_ids:list[str]|None=None) -> dict:
        parent_ids=parent_ids or []; aid=str(uuid.uuid4()); digest=hashlib.sha256(canonical(content).encode()).hexdigest(); revision=self.conn.execute("SELECT COALESCE(MAX(revision),0)+1 FROM artifacts WHERE project_id=? AND artifact_type=?",(pid,kind)).fetchone()[0]
        directory=self.artifact_root/pid; directory.mkdir(parents=True,exist_ok=True); path=directory/f"{revision:03d}_{kind}.json"
        envelope={"artifact_id":aid,"project_id":pid,"artifact_type":kind,"schema_version":"1.0","revision":revision,"created_by":created_by,"created_at":utcnow(),"content_hash":digest,"storage_path":str(path),"parent_artifact_ids":parent_ids,"content":content}
        path.write_text(json.dumps(envelope,indent=2),encoding="utf-8")
        self.conn.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,pid,kind,"1.0",revision,created_by,str(path),digest,canonical(parent_ids),envelope["created_at"])); self.event(pid,"artifact_created",created_by,{"artifact_id":aid,"artifact_type":kind,"hash":digest}); self.conn.commit(); return envelope
    def latest_artifact(self,pid:str,kind:str)->dict|None:
        row=self.conn.execute("SELECT storage_path FROM artifacts WHERE project_id=? AND artifact_type=? ORDER BY revision DESC LIMIT 1",(pid,kind)).fetchone(); return json.loads(Path(row[0]).read_text()) if row else None
    def artifacts(self,pid:str)->list[dict]: return [dict(x) for x in self.conn.execute("SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at",(pid,))]
    def approve(self,pid:str,subject_type:str,subject_id:str,decision="approved",comment="") -> None:
        self.conn.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),pid,subject_type,subject_id,decision,comment,utcnow())); self.event(pid,"user_approval_recorded","user",{"subject_type":subject_type,"subject_id":subject_id,"decision":decision}); self.conn.commit()
    def approved(self,pid:str,subject_type:str,subject_id:str)->bool: return bool(self.conn.execute("SELECT 1 FROM approvals WHERE project_id=? AND subject_type=? AND subject_id=? AND decision='approved'",(pid,subject_type,subject_id)).fetchone())
    def cancel(self,pid:str)->None: self.transition(pid,State.CANCELLED,"user")
    def close(self)->None: self.conn.close()
