import asyncio
import json
import os
import re
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 开发期先用 *，上线建议改成具体域名
    allow_credentials=True,
    allow_methods=["*"],          # 允许 OPTIONS/POST/GET...
    allow_headers=["*"],          # 允许 Content-Type 等
)


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
    cmd = ["python", "cli.py", "--demand", req.demand]
    if req.example_path is not None and req.example_path.strip():
        cmd += ["--example", req.example_path]
    
    print(f"[server] 执行命令: {cmd}")

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
        raise HTTPException(status_code=500, detail=error_msg)

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
        raise HTTPException(status_code=500, detail=error_msg)

    RUNS[run_id] = {"proc": proc, "log_path": log_path}
    return {"run_id": run_id, "log_path": log_path}


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
        yield f"event: meta\ndata: {json.dumps({'run_id': run_id, 'log_path': log_path, 'ts': ts}, ensure_ascii=False)}\n\n"
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