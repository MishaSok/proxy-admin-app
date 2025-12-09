import hashlib
from fastapi import HTTPException, status, Depends, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse

security = HTTPBasic()

# Данные для аутентификации пользователей
USERS = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "user": hashlib.sha256("user123".encode()).hexdigest()
}

def verify_user_credentials(credentials: HTTPBasicCredentials) -> bool:
    """Проверяет имя пользователя и пароль"""
    username = credentials.username
    password_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
    return USERS.get(username) == password_hash

async def authenticate_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Функция зависимости для аутентификации пользователя"""
    if not verify_user_credentials(credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

async def logout_user():
    """Функция для выхода пользователя"""
    # В случае Basic аутентификации, "выход" реализуется отправкой
    # неверных credentials при следующем запросе
    return True