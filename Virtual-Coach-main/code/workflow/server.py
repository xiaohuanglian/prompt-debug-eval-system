import asyncio
import json
import os
import re
import sys
from ipaddress import ip_address
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

WORKFLOW_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = WORKFLOW_DIR / "example"
app = FastAPI()

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "[::1]"],
)


@app.middleware("http")
async def require_local_request(request: Request, call_next):
    """This unauthenticated development service is restricted to this machine."""
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    origin = request.headers.get("origin")
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    if (not local or (origin is not None and origin != expected_origin)
            or request.headers.get("sec-fetch-site") == "cross-site"):
        return JSONResponse(status_code=403, content={"detail": "Local same-origin access only"})
    return await call_next(request)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(WORKFLOW_DIR / "workflow.html")


RUNS: Dict[str, Dict[str, Any]] = {}  # run_id -> {proc, log_path}


class StartReq(BaseModel):
    demand: str
    example_path: Optional[str] = ""


async def _read_kv_from_stdout(proc: asyncio.subprocess.Process, key: str, timeout_s: float = 5.0) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=(.+)$")
    collected_lines = []  # 收集所有输出用于调试
    
    async def _read_loop():
        while True:
            line = await proc.stdout.readline()
            if not line:
                # 如果进程已经结束，检查退出码
                if proc.returncode is not None:
                    break
                continue
            text = line.decode("utf-8", errors="ignore").strip()
            collected_lines.append(text)
            m = pattern.match(text)
            if m:
                return m.group(1).strip()
        return None
    
    try:
        result = await asyncio.wait_for(_read_loop(), timeout=timeout_s)
        if result:
            return result
    except asyncio.TimeoutError:
        pass
    
    # 如果进程已结束且有错误，收集剩余输出
    if proc.returncode is not None and proc.returncode != 0:
        try:
            remaining = await proc.stdout.read()
            if remaining:
                collected_lines.extend(remaining.decode("utf-8", errors="ignore").splitlines())
        except:
            pass
    
    error_msg = f"无法从 cli.py stdout 获取 {key}=...（请确认 cli.py 已 print({key}=...) 并 flush=True）"
    if collected_lines:
        error_msg += f"\n子进程输出:\n" + "\n".join(collected_lines[-10:])  # 只显示最后10行
    raise RuntimeError(error_msg)


@app.post("/api/start")
async def start(req: StartReq):
    # 用参数方式启动 cli，避免 stdin 交互不稳定
    cmd = [sys.executable, "cli.py", "--demand", req.demand]
    if req.example_path is not None and req.example_path.strip():
        example = (WORKFLOW_DIR / req.example_path).resolve()
        if (not example.is_relative_to(EXAMPLES_DIR.resolve())
                or example.suffix.lower() != ".json" or not example.is_file()):
            raise HTTPException(status_code=400, detail="Example must be a JSON file in the example directory")
        cmd += ["--example", str(example)]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
    except Exception as e:
        error_msg = f"无法启动子进程: {str(e)}"
        print(f"[server] 错误: {error_msg}")
        raise HTTPException(status_code=500, detail="Unable to start workflow; inspect local server logs")

    try:
        run_id = await _read_kv_from_stdout(proc, "RUN_ID", timeout_s=5.0)
        log_path = await _read_kv_from_stdout(proc, "LOG_JSONL", timeout_s=5.0)
        print(f"[server] 成功获取 run_id={run_id}, log_path={log_path}")
    except Exception as e:
        # 尝试终止进程
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except:
            try:
                proc.kill()
            except:
                pass
        
        error_msg = str(e)
        print(f"[server] 错误: {error_msg}")
        raise HTTPException(status_code=500, detail="Workflow startup failed; inspect local server logs")

    RUNS[run_id] = {"proc": proc, "log_path": str(WORKFLOW_DIR / log_path)}
    return {"run_id": run_id, "log_path": Path(log_path).name}


async def tail_lines(path: str, poll: float = 0.2):
    # 等待文件出现
    while not os.path.exists(path):
        await asyncio.sleep(poll)

    with open(path, "r", encoding="utf-8") as f:
        # 如果你希望“只看新增”，用 seek 到末尾：
        # f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                await asyncio.sleep(poll)


@app.get("/api/stream/{run_id}")
async def stream(run_id: str):
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="run_id not found")

    log_path = info["log_path"]

    async def event_gen():
        # meta
        from datetime import datetime
        import time
        ts = datetime.fromtimestamp(time.time()).isoformat(sep=" ", timespec="seconds")
        yield f"event: meta\ndata: {json.dumps({'run_id': run_id, 'log_path': Path(log_path).name, 'ts': ts}, ensure_ascii=False)}\n\n"
        async for line in tail_lines(log_path):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                obj = {"run_id": run_id, "ts": "", "type": "raw", "payload": {"line": line}}

            yield f"event: log\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
