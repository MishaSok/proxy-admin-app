from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import time
from main import get_system_info_cached
from auth_session import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, response: Response, username: str = Depends(get_current_user)):
    return await main_dashboard(request, response, username)


@router.get("/main", response_class=HTMLResponse)
async def main_dashboard(request: Request, response: Response, username: str = Depends(get_current_user)):
    # Получаем системную информацию
    info = await get_system_info_cached()

    # Получаем параметры сообщений из query string
    message = request.query_params.get("message", "")
    message_type = request.query_params.get("message_type", "")

    context = {
        "request": request,
        "username": username,
        "info": info,
        "message": message,
        "message_type": message_type,
        "current_page": "main",
        "timestamp": time.strftime('%H:%M:%S', time.localtime())
    }
    return templates.TemplateResponse("main.html", context)
