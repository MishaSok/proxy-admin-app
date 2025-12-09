import os
import platform
import socket
import psutil
import asyncio
import time
import requests
import hashlib
from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="System Monitor")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")

# Кэш для системной информации
_system_info_cache = None
_cache_time = 0
_CACHE_TTL = 5


def get_system_info_sync():
    info = {}
    info['os'] = platform.system()
    info['os_release'] = platform.release()
    info['os_version'] = platform.version()
    info['architecture'] = platform.machine()
    info['hostname'] = socket.gethostname()
    try:
        info['local_ip'] = socket.gethostbyname(info['hostname'])
    except:
        info['local_ip'] = '127.0.0.1'

    info['cpu_count'] = psutil.cpu_count(logical=False) or 0
    info['cpu_count_logical'] = psutil.cpu_count(logical=True) or 0
    freq = psutil.cpu_freq()
    info['cpu_freq'] = round(freq.max, 2) if freq else 'N/A'
    info['cpu_percent'] = psutil.cpu_percent()

    mem = psutil.virtual_memory()
    info['ram_total_gb'] = round(mem.total / (1024 ** 3), 2)
    info['ram_used_gb'] = round(mem.used / (1024 ** 3), 2)
    info['ram_percent'] = mem.percent

    disk = psutil.disk_usage('/')
    info['disk_total_gb'] = round(disk.total / (1024 ** 3), 2)
    info['disk_used_gb'] = round(disk.used / (1024 ** 3), 2)
    info['disk_percent'] = disk.percent

    info['python_version'] = platform.python_version()
    return info


async def check_internet_async(timeout=3):
    def _sync_check():
        try:
            session = requests.Session()
            response = session.get('https://google.com', timeout=2)
            return response.status_code == 200
        except Exception as Error:
            print(f"Internet check error: {Error}")
            return False

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_check)


async def get_system_info_cached():
    global _system_info_cache, _cache_time
    now = time.time()

    if _system_info_cache is None or (now - _cache_time) > _CACHE_TTL:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, get_system_info_sync)
        info['internet'] = await check_internet_async()
        _system_info_cache = info
        _cache_time = now

    return _system_info_cache


@app.on_event("startup")
async def warm_up_cpu_percent():
    await asyncio.get_event_loop().run_in_executor(None, psutil.cpu_percent, 0.1)


# Импортируем маршруты
from routes import main, proxy, pproxy, auth

# Подключаем маршруты
app.include_router(main.router)
app.include_router(proxy.router)
app.include_router(pproxy.router)
app.include_router(auth.router)


# Экспортируем функции для использования в маршрутах
@app.get("/system-info")
async def get_system_info():
    return await get_system_info_cached()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
