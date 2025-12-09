from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import hashlib
import platform
import os
import subprocess
import requests
from auth_session import get_current_user
from main import get_system_info_cached
from fastapi.templating import Jinja2Templates
from typing import Dict, Tuple, List
import configparser

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Пароль для защиты изменения прокси
PROXY_PASSWORD_HASH = hashlib.sha256("admin".encode()).hexdigest()

# Пути к конфигурационным файлам
GNOME_PROXY_SCHEMA = "org.gnome.system.proxy"
ENVIRONMENT_FILE = "/etc/environment"
SYSTEMD_ENVIRONMENT_DIR = "/etc/systemd/system.conf.d/"
APT_CONFIG_FILE = "/etc/apt/apt.conf.d/95proxies"


def verify_password(password: str) -> bool:
    """Проверяет пароль для изменения прокси"""
    return hashlib.sha256(password.encode()).hexdigest() == PROXY_PASSWORD_HASH


def run_command(cmd: List[str]) -> Tuple[bool, str]:
    """Выполняет системную команду и возвращает результат"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Ошибка выполнения команды: {e.stderr}"
    except Exception as e:
        return False, f"Ошибка: {str(e)}"


def set_gnome_proxy(proxy_type: str, server: str, port: str = "", enable: bool = True):
    """Устанавливает прокси через GNOME settings (для графического интерфейса)"""
    try:
        if enable:
            # Включаем автоматическое определение прокси (отключаем ручные настройки)
            run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}", "mode", "manual"])

            if proxy_type == "http":
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.http", "host", server.split(":")[0]])
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.http", "port",
                             port or server.split(":")[1] if ":" in server else "8080"])
            elif proxy_type == "https":
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.https", "host", server.split(":")[0]])
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.https", "port",
                             port or server.split(":")[1] if ":" in server else "8080"])
            elif proxy_type == "ftp":
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.ftp", "host", server.split(":")[0]])
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.ftp", "port",
                             port or server.split(":")[1] if ":" in server else "8080"])
            elif proxy_type == "socks":
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.socks", "host", server.split(":")[0]])
                run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}.socks", "port",
                             port or server.split(":")[1] if ":" in server else "8080"])
        else:
            # Отключаем прокси
            run_command(["gsettings", "set", f"{GNOME_PROXY_SCHEMA}", "mode", "none"])

        return True, "Настройки GNOME прокси обновлены"
    except Exception as e:
        return False, f"Ошибка настройки GNOME прокси: {str(e)}"


def set_environment_proxy(server: str, no_proxy: str = "", enable: bool = True):
    """Устанавливает прокси через переменные окружения системы"""
    try:
        env_lines = []

        # Читаем существующий файл
        if os.path.exists(ENVIRONMENT_FILE):
            with open(ENVIRONMENT_FILE, 'r') as f:
                env_lines = f.readlines()

        # Удаляем старые настройки прокси
        new_lines = []
        proxy_vars = ['http_proxy', 'https_proxy', 'ftp_proxy', 'all_proxy',
                      'HTTP_PROXY', 'HTTPS_PROXY', 'FTP_PROXY', 'ALL_PROXY', 'no_proxy', 'NO_PROXY']

        for line in env_lines:
            if not any(line.strip().startswith(f"{var}=") for var in proxy_vars):
                new_lines.append(line)

        # Добавляем новые настройки если включено
        if enable and server:
            http_server = server if server.startswith('http') else f'http://{server}'
            https_server = server if server.startswith('http') else f'https://{server}'

            proxy_settings = [
                f"http_proxy={http_server}\n",
                f"https_proxy={https_server}\n",
                f"ftp_proxy={http_server}\n",
                f"HTTP_PROXY={http_server}\n",
                f"HTTPS_PROXY={https_server}\n",
                f"FTP_PROXY={http_server}\n"
            ]

            if no_proxy:
                proxy_settings.append(f"no_proxy={no_proxy}\n")
                proxy_settings.append(f"NO_PROXY={no_proxy}\n")

            new_lines.extend(proxy_settings)

        # Записываем обратно (требует прав sudo)
        success, msg = run_command(["sudo", "tee", ENVIRONMENT_FILE] + new_lines)
        if not success:
            return False, msg

        # Обновляем переменные окружения текущей сессии
        if enable and server:
            http_server = server if server.startswith('http') else f'http://{server}'
            os.environ['http_proxy'] = http_server
            os.environ['https_proxy'] = http_server
            os.environ['HTTP_PROXY'] = http_server
            os.environ['HTTPS_PROXY'] = http_server
            if no_proxy:
                os.environ['no_proxy'] = no_proxy
                os.environ['NO_PROXY'] = no_proxy
        else:
            for var in proxy_vars:
                os.environ.pop(var, None)

        return True, "Системные переменные прокси обновлены"
    except Exception as e:
        return False, f"Ошибка настройки переменных окружения: {str(e)}"


def set_apt_proxy(server: str, enable: bool = True):
    """Настраивает прокси для apt package manager"""
    try:
        if not enable:
            # Удаляем файл конфигурации apt прокси
            if os.path.exists(APT_CONFIG_FILE):
                run_command(["sudo", "rm", APT_CONFIG_FILE])
            return True, "Прокси для APT отключен"

        if not server:
            return False, "Для APT прокси требуется указать сервер"

        apt_config = []
        if server.startswith('http'):
            apt_config.append(f'Acquire::http::proxy "{server}";\n')
            apt_config.append(f'Acquire::https::proxy "{server}";\n')
            apt_config.append(f'Acquire::ftp::proxy "{server}";\n')
        else:
            apt_config.append(f'Acquire::http::proxy "http://{server}";\n')
            apt_config.append(f'Acquire::https::proxy "https://{server}";\n')
            apt_config.append(f'Acquire::ftp::proxy "http://{server}";\n')

        # Создаем директорию если не существует
        run_command(["sudo", "mkdir", "-p", os.path.dirname(APT_CONFIG_FILE)])

        # Записываем конфигурацию
        success, msg = run_command(["sudo", "tee", APT_CONFIG_FILE] + apt_config)
        if not success:
            return False, msg

        return True, "Прокси для APT настроен"
    except Exception as e:
        return False, f"Ошибка настройки APT прокси: {str(e)}"


def set_linux_proxy(server: str, bypass_list: str = "", enable: bool = True):
    """Устанавливает настройки прокси в Linux"""
    messages = []

    # 1. Настройка GNOME прокси (для графической среды)
    success, msg = set_gnome_proxy("http", server, "", enable)
    messages.append(f"GNOME: {msg}")

    # 2. Настройка системных переменных
    success, msg = set_environment_proxy(server, bypass_list, enable)
    messages.append(f"Environment: {msg}")

    # 3. Настройка APT прокси
    success, msg = set_apt_proxy(server, enable)
    messages.append(f"APT: {msg}")

    return True, " | ".join(messages)


def disable_linux_proxy():
    """Отключает прокси в Linux"""
    messages = []

    # 1. Отключаем GNOME прокси
    success, msg = set_gnome_proxy("http", "", "", False)
    messages.append(f"GNOME: {msg}")

    # 2. Отключаем системные переменные
    success, msg = set_environment_proxy("", "", False)
    messages.append(f"Environment: {msg}")

    # 3. Отключаем APT прокси
    success, msg = set_apt_proxy("", False)
    messages.append(f"APT: {msg}")

    return True, " | ".join(messages)


def get_gnome_proxy_settings():
    """Получает настройки прокси из GNOME"""
    proxy_settings = {}
    try:
        # Проверяем режим прокси
        success, mode = run_command(["gsettings", "get", f"{GNOME_PROXY_SCHEMA}", "mode"])
        if success:
            proxy_settings['GNOME_Mode'] = mode.strip().strip("'")

        # Получаем настройки для каждого типа прокси
        proxy_types = ['http', 'https', 'ftp', 'socks']
        for ptype in proxy_types:
            success, host = run_command(["gsettings", "get", f"{GNOME_PROXY_SCHEMA}.{ptype}", "host"])
            success, port = run_command(["gsettings", "get", f"{GNOME_PROXY_SCHEMA}.{ptype}", "port"])

            if success and host.strip() != "''":
                proxy_settings[f'GNOME_{ptype.upper()}_Proxy'] = f"{host.strip().strip("'")}:{port.strip()}"

        return proxy_settings
    except Exception as e:
        proxy_settings['GNOME_Error'] = f"Ошибка чтения GNOME настроек: {str(e)}"
        return proxy_settings


def get_environment_proxy_settings():
    """Получает настройки прокси из переменных окружения"""
    env_proxy_vars = [
        'HTTP_PROXY', 'http_proxy',
        'HTTPS_PROXY', 'https_proxy',
        'FTP_PROXY', 'ftp_proxy',
        'ALL_PROXY', 'all_proxy',
        'NO_PROXY', 'no_proxy'
    ]

    env_proxies = {}
    for var in env_proxy_vars:
        # Сначала проверяем текущие переменные окружения
        value = os.environ.get(var, '')
        if not value and os.path.exists(ENVIRONMENT_FILE):
            # Если не найдено, ищем в /etc/environment
            try:
                with open(ENVIRONMENT_FILE, 'r') as f:
                    for line in f:
                        if line.startswith(f"{var}="):
                            value = line.split('=', 1)[1].strip()
                            break
            except:
                pass
        env_proxies[var] = value

    return env_proxies


def get_apt_proxy_settings():
    """Получает настройки прокси для APT"""
    apt_proxies = {}
    try:
        if os.path.exists(APT_CONFIG_FILE):
            with open(APT_CONFIG_FILE, 'r') as f:
                content = f.read()
                if 'http::proxy' in content:
                    apt_proxies['APT_HTTP_Proxy'] = content.split('http::proxy "', 1)[1].split('"', 1)[0]
                if 'https::proxy' in content:
                    apt_proxies['APT_HTTPS_Proxy'] = content.split('https::proxy "', 1)[1].split('"', 1)[0]
    except Exception as e:
        apt_proxies['APT_Error'] = f"Ошибка чтения APT настроек: {str(e)}"

    return apt_proxies


def get_linux_proxy_settings():
    """Получает настройки прокси из всех источников в Linux"""
    proxy_settings = {}

    # GNOME настройки
    proxy_settings['gnome_settings'] = get_gnome_proxy_settings()

    # Переменные окружения
    proxy_settings['environment_variables'] = get_environment_proxy_settings()

    # APT настройки
    proxy_settings['apt_settings'] = get_apt_proxy_settings()

    return proxy_settings


def get_proxy_info():
    """Получает информацию о прокси из всех возможных источников"""
    proxy_info = {}

    if platform.system() == "Linux":
        proxy_info['linux_settings'] = get_linux_proxy_settings()

    # Переменные окружения текущего процесса
    env_proxy_vars = [
        'HTTP_PROXY', 'http_proxy',
        'HTTPS_PROXY', 'https_proxy',
        'FTP_PROXY', 'ftp_proxy',
        'ALL_PROXY', 'all_proxy',
        'NO_PROXY', 'no_proxy'
    ]

    env_proxies = {}
    for var in env_proxy_vars:
        env_proxies[var] = os.environ.get(var, '')
    proxy_info['current_environment'] = env_proxies

    # Настройки из requests
    proxy_info['requests_proxies'] = requests.utils.getproxies()
    return proxy_info


def format_proxy_info(proxy_info):
    """Форматирует информацию о прокси для HTML"""
    html_parts = []

    # Текущие переменные окружения
    html_parts.append("<h5>📝 Текущие переменные окружения</h5>")
    env_vars = proxy_info.get('current_environment', {})
    env_found = False
    for key, value in env_vars.items():
        if value:
            html_parts.append(f"<p><strong>{key}:</strong> {value}</p>")
            env_found = True
    if not env_found:
        html_parts.append("<p class='text-muted'>Не настроены</p>")

    # Настройки Linux
    if 'linux_settings' in proxy_info:
        html_parts.append("<h5>🐧 Настройки Linux</h5>")
        linux_settings = proxy_info['linux_settings']

        # GNOME настройки
        gnome_settings = linux_settings.get('gnome_settings', {})
        if gnome_settings:
            html_parts.append("<h6>GNOME Settings:</h6>")
            mode = gnome_settings.get('GNOME_Mode', 'none')
            status_text = "Ручной" if mode == "manual" else "Авто" if mode == "auto" else "Выкл"
            status_class = "text-success" if mode == "manual" else "text-warning" if mode == "auto" else "text-danger"
            html_parts.append(f"<p><strong>Режим:</strong> <span class='{status_class}'>{status_text}</span></p>")

            for key, value in gnome_settings.items():
                if key not in ['GNOME_Mode', 'GNOME_Error'] and value:
                    html_parts.append(f"<p><strong>{key}:</strong> {value}</p>")

        # APT настройки
        apt_settings = linux_settings.get('apt_settings', {})
        if apt_settings:
            html_parts.append("<h6>APT Settings:</h6>")
            for key, value in apt_settings.items():
                if key != 'APT_Error' and value:
                    html_parts.append(f"<p><strong>{key}:</strong> {value}</p>")

        # Системные переменные из /etc/environment
        env_settings = linux_settings.get('environment_variables', {})
        if any(env_settings.values()):
            html_parts.append("<h6>Системные переменные (/etc/environment):</h6>")
            for key, value in env_settings.items():
                if value:
                    html_parts.append(f"<p><strong>{key}:</strong> {value}</p>")

    # Настройки, используемые requests
    html_parts.append("<h5>🔧 Используемые прокси (requests)</h5>")
    requests_proxies = proxy_info.get('requests_proxies', {})
    if requests_proxies:
        for scheme, proxy_url in requests_proxies.items():
            html_parts.append(f"<p><strong>{scheme}:</strong> {proxy_url}</p>")
    else:
        html_parts.append("<p class='text-muted'>Не обнаружены</p>")

    return "\n".join(html_parts)


@router.get("/proxy", response_class=HTMLResponse)
async def proxy_settings(request: Request, response: Response, username: str = Depends(get_current_user)):
    proxy_info = get_proxy_info()
    proxy_html = format_proxy_info(proxy_info)

    # Получаем текущие настройки для предзаполнения формы
    current_server = ""
    current_bypass = ""

    linux_settings = proxy_info.get('linux_settings', {})
    env_settings = linux_settings.get('environment_variables', {})

    # Ищем текущий прокси сервер
    for key in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']:
        if env_settings.get(key):
            current_server = env_settings[key]
            break

    # Ищем текущие исключения
    for key in ['no_proxy', 'NO_PROXY']:
        if env_settings.get(key):
            current_bypass = env_settings[key]
            break

    context = {
        "request": request,
        "username": username,
        "current_page": "proxy",
        "proxy_html": proxy_html,
        "current_server": current_server,
        "current_bypass": current_bypass,
        "message": request.query_params.get("message", ""),
        "message_type": request.query_params.get("message_type", "")
    }
    return templates.TemplateResponse("proxy.html", context)


@router.post("/set-proxy")
async def set_proxy(
        request: Request,
        response: Response,
        proxy_server: str = Form(""),
        proxy_bypass: str = Form(""),
        password: str = Form(...),
        action: str = Form(...),
        username: str = Depends(get_current_user)
):
    message = ""
    message_type = "success"

    if not verify_password(password):
        return RedirectResponse(url="/proxy?message=Неверный пароль&message_type=danger", status_code=303)

    try:
        if platform.system() != "Linux":
            return RedirectResponse(
                url="/proxy?message=Функция доступна только для Linux&message_type=danger",
                status_code=303
            )

        if action == "enable":
            if not proxy_server:
                return RedirectResponse(
                    url="/proxy?message=Укажите адрес прокси-сервера&message_type=danger",
                    status_code=303
                )
            success, msg = set_linux_proxy(proxy_server, proxy_bypass, True)
        elif action == "disable":
            success, msg = disable_linux_proxy()
        elif action == "update":
            if not proxy_server:
                return RedirectResponse(
                    url="/proxy?message=Укажите адрес прокси-сервера&message_type=danger",
                    status_code=303
                )
            success, msg = set_linux_proxy(proxy_server, proxy_bypass, True)
        else:
            success, msg = False, "Неизвестное действие"

        if success:
            message = msg
            message_type = "success"
        else:
            message = msg
            message_type = "danger"

    except Exception as e:
        message = f"Ошибка: {str(e)}"
        message_type = "danger"

    return RedirectResponse(url=f"/proxy?message={message}&message_type={message_type}", status_code=303)