# Proxy Admin / Панель управления прокси

English below ↓ / Русская версия выше ↑

## О проекте (RU)
Удобная веб‑панель на FastAPI для мониторинга системы и управления прокси (включая pproxy) прямо из браузера.

### Возможности
- Системная информация: CPU, RAM, диск, сеть, версия Python, интернет‑доступ.
- Прокси (Linux): GNOME, переменные окружения, APT.
- PProxy: запуск команд, пресеты, статус/версия, установка в локальный venv без затрагивания системного Python (обход PEP 668).
- Аутентификация по сессиям (cookie); Basic используется только при первичном входе.

### Требования
- Python 3.12+
- Linux / macOS / Windows (для pproxy: venv на *nix, pip на Windows).

### Установка и запуск
```bash
git clone <repo-url>
cd ProxyAdmin
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Доступ и логины
- URL: `http://localhost:8000`
- Тестовые учётки: `admin/admin123`, `user/user123`.

### Структура
- `app/main.py` — инициализация FastAPI, статика, шаблоны, системная инфо.
- `app/routes/` — `main`, `proxy`, `pproxy`, `auth`.
- `app/auth_session.py` — сессии и куки.
- `app/templates/` — HTML (Bootstrap 5).

### PProxy
- Статус: `/pproxy/status` учитывает локальный venv `.pproxy-venv`.
- Установка: Linux/macOS — `.pproxy-venv`; Windows — `python -m pip install --upgrade pproxy`.
- Запуск: UI подставляет путь до установленного pproxy (включая локальный venv).

### Безопасность
- Сессии в памяти (для продакшена — Redis/БД).
- Cookie `session_id`: `httponly`, `samesite=lax`; включите `secure=True` при HTTPS.
- Не храните тестовые пароли в продакшене.

---

## About (EN)
A FastAPI web panel for system monitoring and proxy management (including pproxy) from the browser.

### Features
- System info: CPU, RAM, disk, network, Python version, internet check.
- Proxy (Linux): GNOME, environment variables, APT.
- PProxy: run commands, presets, status/version, install into a local venv to avoid touching system Python (PEP 668 friendly).
- Session-based auth via cookies (Basic only for the initial login).

### Requirements
- Python 3.12+
- Linux / macOS / Windows (pproxy install: venv on *nix, pip on Windows).

### Install & Run
```bash
git clone <repo-url>
cd ProxyAdmin
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r app/requirements.txt
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Access & Logins
- URL: `http://localhost:8000`
- Test users: `admin/admin123`, `user/user123`.

### Structure
- `app/main.py` — FastAPI init, static, templates, system info.
- `app/routes/` — `main`, `proxy`, `pproxy`, `auth`.
- `app/auth_session.py` — session auth & cookies.
- `app/templates/` — HTML (Bootstrap 5).

### PProxy
- Status: `/pproxy/status` checks system and local `.pproxy-venv`.
- Install: Linux/macOS — `.pproxy-venv`; Windows — `python -m pip install --upgrade pproxy`.
- Run: UI injects the resolved pproxy path (supports local venv).

### Security
- Sessions in memory (use Redis/DB for production).
- `session_id` cookie: `httponly`, `samesite=lax`; set `secure=True` with HTTPS.
- Do not keep test credentials in production.

## License
MIT (replace if needed).