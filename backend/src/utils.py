"""Вспомогательные функции бэкенда."""
import socket
from typing import Optional
from fastapi import Request

def _get_lan_ip() -> str:
    """Определяет локальный сетевой IP машины (например, 192.168.x.x)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Соединение не отправляет пакеты, только определяет маршрут по умолчанию
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

def get_client_ip(http_request: Request) -> Optional[str]:
    """IP клиента; для localhost возвращается реальный сетевой IP машины."""
    host = http_request.client.host if http_request.client else None
    if host in ("127.0.0.1", "::1", "localhost"):
        return _get_lan_ip()
    return host