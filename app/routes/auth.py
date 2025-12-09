from fastapi import APIRouter, Request, Response, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from auth_session import get_current_user, auth_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Отображает страницу входа или редиректит, если сессия активна"""
    session_id = request.cookies.get("session_id")
    if session_id and auth_manager.validate_session(session_id):
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, response: Response):
    """Создает сессию по присланным учетным данным"""
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Не указаны логин или пароль")

    if not auth_manager.verify_plain_credentials(username, password):
        return JSONResponse({"success": False, "message": "Неверный логин или пароль"}, status_code=401)

    session_id = auth_manager.create_session(username)
    resp = JSONResponse({"success": True})
    resp.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=24 * 60 * 60,
        secure=False,  # В проде включить HTTPS
        samesite="lax"
    )
    return resp


@router.get("/logout")
async def logout(request: Request, response: Response, username: str = Depends(get_current_user)):
    """
    Выход из системы - удаляет сессию
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        auth_manager.delete_session(session_id)

    # Очищаем куки
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")

    return response