"""Small local WSGI API for project lifecycle operations.

The surface intentionally exposes only orchestrator-controlled operations; it
does not expose filesystem, shell, simulator-command, or arbitrary tool APIs.
"""
from __future__ import annotations
import json
from http import HTTPStatus
from typing import Callable
from urllib.parse import unquote
from wsgiref.simple_server import make_server

from .domain import ApprovalRequired
from .chat import respond
from .orchestrator import Orchestrator
from .storage import ProjectStore
from .web import dashboard_html

class ProjectApi:
    def __init__(self, store: ProjectStore, orchestrator: Orchestrator | None = None):
        self.store=store; self.orchestrator=orchestrator or Orchestrator(store)
    def dispatch(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        payload=payload or {}; parts=[unquote(part) for part in path.strip("/").split("/") if part]
        try:
            if method=="POST" and parts==["projects"]:
                return HTTPStatus.CREATED, {"project_id":self.store.create_project(payload)}
            if parts==["settings","model"]:
                if method=="GET": return HTTPStatus.OK,self.store.model_settings()
                if method=="PUT": return HTTPStatus.OK,self.store.save_model_settings(payload.get("provider"),payload.get("model"),payload.get("api_key",""),payload.get("base_url",""),payload.get("temperature",0.1),payload.get("max_tokens",4096),payload.get("enabled",True),payload.get("clear_api_key",False))
            if method=="POST" and parts==["chat"]: return HTTPStatus.OK,respond(self.store,payload.get("message"))
            if len(parts) >= 2 and parts[0]=="projects":
                pid=parts[1]
                if method=="GET" and len(parts)==2: return HTTPStatus.OK, self.store.project(pid)
                if method=="POST" and parts[2:]==["run"]: return HTTPStatus.OK, self.orchestrator.run(pid)
                if method=="POST" and parts[2:]==["approvals"]:
                    subject=payload.get("subject"); revision=payload.get("revision")
                    if subject not in {"design","optimization"} or not isinstance(revision,int): return HTTPStatus.BAD_REQUEST,{"error":"subject (design|optimization) and integer revision are required"}
                    self.store.approve(pid,subject,str(revision),payload.get("decision","approved"),payload.get("comment","")); return HTTPStatus.CREATED,{"status":"recorded"}
                if method=="POST" and parts[2:]==["resume"]: return HTTPStatus.OK, self.orchestrator.resume(pid)
                if method=="POST" and parts[2:]==["cancel"]: self.store.cancel(pid); return HTTPStatus.OK,self.store.project(pid)
                if method=="GET" and parts[2:]==["artifacts"]: return HTTPStatus.OK,{"artifacts":self.store.artifacts(pid)}
                if method=="GET" and parts[2:]==["events"]: return HTTPStatus.OK,{"events":self.store.events(pid)}
            return HTTPStatus.NOT_FOUND,{"error":"route not found"}
        except KeyError as exc: return HTTPStatus.NOT_FOUND,{"error":str(exc)}
        except ApprovalRequired as exc: return HTTPStatus.CONFLICT,{"error":str(exc)}
        except (ValueError,TypeError) as exc: return HTTPStatus.BAD_REQUEST,{"error":str(exc)}
    def __call__(self,environ:dict,start_response:Callable):
        if environ["REQUEST_METHOD"] == "GET" and environ["PATH_INFO"] == "/":
            encoded=dashboard_html().encode("utf-8")
            start_response("200 OK",[("Content-Type","text/html; charset=utf-8"),("Content-Length",str(len(encoded)))])
            return [encoded]
        try:
            length=int(environ.get("CONTENT_LENGTH") or 0); raw=environ["wsgi.input"].read(length) if length else b""
            payload=json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError,UnicodeDecodeError):
            status,body=HTTPStatus.BAD_REQUEST,{"error":"request body must be valid JSON"}
        else: status,body=self.dispatch(environ["REQUEST_METHOD"],environ["PATH_INFO"],payload)
        encoded=json.dumps(body,default=str).encode("utf-8"); start_response(f"{int(status)} {HTTPStatus(status).phrase}",[("Content-Type","application/json"),("Content-Length",str(len(encoded)))])
        return [encoded]

def serve(store:ProjectStore,host:str="127.0.0.1",port:int=8000)->None:
    print(f"Circuit Agent API listening on http://{host}:{port}")
    make_server(host,port,ProjectApi(store)).serve_forever()
