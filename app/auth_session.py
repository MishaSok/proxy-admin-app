import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Request, Response, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Данные для аутентификации пользователей
USERS = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "user": hashlib.sha256("user123".encode()).hexdigest()
}

# Хранилище сессий (в продакшн используйте Redis или базу данных)
sessions = {}


class SessionAuth:
    def __init__(self):
        self.security = HTTPBasic()

    def verify_user_credentials(self, credentials: HTTPBasicCredentials) -> bool:
        """Проверяет имя пользователя и пароль из Basic заголовка"""
        username = credentials.username
        password_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
        return USERS.get(username) == password_hash

    def verify_plain_credentials(self, username: str, password: str) -> bool:
        """Проверяет имя пользователя и пароль из формы"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return USERS.get(username) == password_hash

    def create_session(self, username: str) -> str:
        """Создает новую сессию"""
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = {
            "username": username,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=24)
        }
        return session_id

    def validate_session(self, session_id: str) -> dict:
        """Проверяет валидность сессии"""
        if session_id not in sessions:
            return None

        session = sessions[session_id]
        if datetime.now() > session["expires_at"]:
            del sessions[session_id]
            return None

        return session

    def delete_session(self, session_id: str):
        """Удаляет сессию"""
        if session_id in sessions:
            del sessions[session_id]

    async def authenticate(self, request: Request, response: Response):
        """Аутентификация пользователя"""
        session_id = request.cookies.get("session_id")

        # Если есть валидная сессия - возвращаем username
        if session_id:
            session = self.validate_session(session_id)
            if session:
                return session["username"]

        # Если нет сессии - проверяем, пришли ли креды явно в заголовке
        auth_header = request.headers.get("Authorization")
        if auth_header:
            credentials = await self.security(request)
            if self.verify_user_credentials(credentials):
                new_session_id = self.create_session(credentials.username)
                response.set_cookie(
                    key="session_id",
                    value=new_session_id,
                    httponly=True,
                    max_age=24 * 60 * 60,  # 24 часа
                    secure=False,  # True в production с HTTPS
                    samesite="lax"
                )
                return credentials.username

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
            )

        # Нет сессии и нет заголовка Authorization - отправляем на страницу логина
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Требуется аутентификация",
            headers={"Location": "/login"},
        )


# Создаем экземпляр аутентификатора
auth_manager = SessionAuth()


# Dependency для использования в маршрутах
async def get_current_user(request: Request, response: Response):
    return await auth_manager.authenticate(request, response)