from fastapi import APIRouter, Request, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from auth_session import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/pproxy", response_class=HTMLResponse)
async def pproxy_terminal(request: Request, response: Response, username: str = Depends(get_current_user)):
    context = {
        "request": request,
        "username": username,
        "current_page": "pproxy"
    }
    return templates.TemplateResponse("pproxy.html", context)
