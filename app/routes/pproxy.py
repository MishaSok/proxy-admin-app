import asyncio
import os
import sys
import shutil
import shlex
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, Request, Depends, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from auth_session import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")
VENV_DIR = Path(__file__).resolve().parent / ".pproxy-venv"


@router.get("/pproxy", response_class=HTMLResponse)
async def pproxy_terminal(request: Request, response: Response, username: str = Depends(get_current_user)):
    context = {
        "request": request,
        "username": username,
        "current_page": "pproxy"
    }
    return templates.TemplateResponse("pproxy.html", context)


def _pproxy_path() -> str | None:
    """Возвращает путь до pproxy если установлен (системно или в локальном venv)"""
    candidates: List[str | None] = [shutil.which("pproxy")]

    # Проверяем локальный venv
    if VENV_DIR.exists():
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        exe_name = "pproxy.exe" if os.name == "nt" else "pproxy"
        local_path = VENV_DIR / bin_dir / exe_name
        candidates.append(str(local_path))

    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


async def _pproxy_version(path: str) -> str:
    """Получает версию pproxy"""
    try:
        proc = await asyncio.create_subprocess_exec(
            path,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return stdout.decode().strip()
    except Exception:
        return "unknown"


@router.get("/pproxy/status")
async def pproxy_status():
    """Проверка наличия pproxy"""
    path = _pproxy_path()
    installed = path is not None
    version = await _pproxy_version(path) if installed else None
    return {"installed": installed, "version": version}


async def _run_step(cmd: List[str], timeout: int = 180) -> Dict[str, str | int | bool]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Команда {' '.join(cmd)} превысила {timeout} секунд и была остановлена",
            "returncode": -1,
        }
    return {
        "success": proc.returncode == 0,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": proc.returncode,
    }


async def _install_pproxy() -> Dict:
    """Устанавливает pproxy:
    - Windows: системный pip
    - Linux/mac: в локальный venv (.pproxy-venv) без трогания системного питона
    """
    logs: List[str] = []
    errors: List[str] = []

    if sys.platform.startswith("win"):
        result = await _run_step(["python", "-m", "pip", "install", "--upgrade", "pproxy"])
        logs.append(result["stdout"])
        if result["stderr"]:
            errors.append(result["stderr"])
        result["stdout"] = "\n".join(filter(None, logs))
        result["stderr"] = "\n".join(filter(None, errors))
        return result

    # Linux / macOS — ставим в локальный venv, чтобы обойти PEP 668
    python_bin = "python3"
    venv_python = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python3")

    steps = [
        [python_bin, "-m", "venv", str(VENV_DIR)],
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pproxy"],
    ]

    last_returncode = 0
    for cmd in steps:
        step = await _run_step(cmd)
        logs.append(step["stdout"])
        if step["stderr"]:
            errors.append(step["stderr"])
        last_returncode = step["returncode"]  # type: ignore
        if not step["success"]:
            break

    return {
        "success": last_returncode == 0 and not errors,
        "stdout": "\n".join(filter(None, logs)),
        "stderr": "\n".join(filter(None, errors)),
        "returncode": last_returncode,
    }


@router.post("/pproxy/install")
async def install_pproxy():
    """Устанавливает pproxy если не установлен"""
    result = await _install_pproxy()
    return JSONResponse(result, status_code=200 if result["success"] else 400)


async def _run_command(command: str) -> Dict:
    """Выполняет команду pproxy и возвращает вывод"""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "success": False,
            "stdout": "",
            "stderr": "Команда превысила лимит в 60 секунд и была остановлена",
            "returncode": -1,
        }

    return {
        "success": proc.returncode == 0,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": proc.returncode,
    }


@router.post("/pproxy/run")
async def run_pproxy_command(request: Request):
    """Запускает pproxy с указанной командой"""
    data = await request.json()
    command = data.get("command", "").strip()

    path = _pproxy_path()
    if not path:
        raise HTTPException(status_code=400, detail="pproxy не установлен")

    if not command:
        raise HTTPException(status_code=400, detail="Не указана команда")

    # Безопасность: разрешаем только команды, начинающиеся с pproxy
    split_cmd = shlex.split(command) if command else []
    first_token = split_cmd[0] if split_cmd else ""
    if "pproxy" not in first_token:
        raise HTTPException(status_code=400, detail="Разрешены только команды pproxy")

    # Подменяем первую часть на конкретный путь, чтобы использовать локальный venv
    split_cmd[0] = f'"{path}"'
    command = " ".join(split_cmd)

    result = await _run_command(command)
    return JSONResponse(result)
