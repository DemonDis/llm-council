"""FastAPI бэкенд для LLM Council."""

import os
import sys
from pathlib import Path

# Модули приложения лежат в backend/src и импортируются «плоско»
# (import storage, from config import ...), поэтому добавляем этот
# каталог в sys.path до остальных импортов.
SRC_DIR = str(Path(__file__).resolve().parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.conversations import router as conversations_router
from routes.messages import router as messages_router

app = FastAPI(title="LLM Council API")

# Включаем CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Обязательно False, если allow_origins=["*"] !
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations_router)
app.include_router(messages_router)


@app.get("/")
async def root():
    """Конечная точка проверки состояния."""
    return {"status": "ok", "service": "LLM Council API"}


if __name__ == "__main__":
    import uvicorn

    backend_dir = str(Path(__file__).resolve().parent)

    # Модули бэкенда импортируются «плоско» (import storage, from config ...),
    # поэтому backend/ и backend/src/ должны быть в пути и в текущем процессе,
    # и в дочернем процессе uvicorn-релоадера (через PYTHONPATH).
    extra_paths = os.pathsep.join([backend_dir, SRC_DIR])
    os.environ["PYTHONPATH"] = extra_paths + os.pathsep + os.environ.get("PYTHONPATH", "")

    uvicorn.run(
        "main:app",  # строка импорта обязательна для reload=True
        host="0.0.0.0",
        port=8001,
        reload=True,
        reload_dirs=[backend_dir],
    )
