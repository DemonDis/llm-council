"""Тест логирования LLM-вызовов против локального фейкового OpenRouter."""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND / "src"))
sys.path.insert(0, str(BACKEND))

import threading  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402

app = FastAPI()


@app.post("/v1/chat/completions")
async def completions(request: Request):
    payload = await request.json()
    if not payload.get("stream"):
        return {
            "choices": [{"message": {"content": "Синхронный ответ", "reasoning_details": None}}]
        }

    async def gen():
        for piece in ["Стрим ", "ответ ", "готов."]:
            yield f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n"
        await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


threading.Thread(
    target=lambda: uvicorn.run(app, host="127.0.0.1", port=8003, log_level="error"),
    daemon=True,
).start()

import openrouter  # noqa: E402
from config import LOGS_DIR  # noqa: E402
from llm_logs import log_llm_call  # noqa: E402

import time  # noqa: E402
time.sleep(1.5)  # даём фейковому серверу подняться

URL = "http://127.0.0.1:8003/v1/chat/completions"
msgs = [
    {"role": "system", "content": "СЕКРЕТНЫЙ_СИСТЕМНЫЙ_ПРОМПТ"},
    {"role": "user", "content": "вопрос"},
]


async def main():
    r = await openrouter.query_model("mock-model", msgs, api_url=URL, api_key="sk-DO_NOT_LOG_123")
    assert r["content"] == "Синхронный ответ"

    parts = []
    async for chunk in openrouter.query_model_stream("mock-model", msgs, api_url=URL, api_key="sk-DO_NOT_LOG_123"):
        assert chunk is not None
        parts.append(chunk["content"])
    assert "".join(parts) == "Стрим ответ готов."

    # Ошибка: неверный URL
    await openrouter.query_model("mock-model", msgs, api_url="http://127.0.0.1:9/nope")


asyncio.run(main())

log_dir = Path(LOGS_DIR)
files = sorted(log_dir.glob("llm_calls_*.jsonl"))
assert files, "лог-файл не создан"
lines = [json.loads(l) for l in files[-1].read_text().splitlines() if l.strip()]
print(f"записей в {files[-1].name}: {len(lines)}")
for rec in lines:
    blob = json.dumps(rec, ensure_ascii=False)
    assert "НЕЛОГИРОВАТЬ" not in blob, "УТЕЧКА КЛЮЧА В ЛОГ!"
    print(" -", rec["stream"], rec["model"], "| resp:", (rec.get("response") or {}).get("content"), "| err:", rec.get("error"))

sync_rec = next(r for r in lines if not r["stream"])
stream_rec = next(r for r in lines if r["stream"] and r.get("response"))
err_rec = next(r for r in lines if r.get("error"))
assert sync_rec["messages"][0]["content"] == "СЕКРЕТНЫЙ_СИСТЕМНЫЙ_ПРОМПТ"
assert stream_rec["response"]["content"] == "Стрим ответ готов."
assert sync_rec["duration_s"] is not None and err_rec["duration_s"] is not None
print("\nLLM LOG TESTS PASSED")
