import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lanl_demo import QUESTIONS, answer, empty, parse_question, read_snapshot


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    if os.getenv("NEO4J_URI"):
        from lanl_neo4j import open_driver

        with open_driver() as driver:
            app.state.driver = driver
            yield
    else:
        app.state.driver = None
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(max_length=1_000)


@app.post("/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        return empty("Bạn chưa nhập câu hỏi.")
    metric, host = parse_question(request.message)
    if metric is None:
        return empty("Bản demo hỗ trợ ba câu hỏi trên mẫu LANL: " + " ".join(QUESTIONS))

    try:
        if app.state.driver is not None:
            from lanl_neo4j import read_case

            case = read_case(app.state.driver, metric)
        else:
            case = read_snapshot(metric)
        return answer(case, host)
    except FileNotFoundError as error:
        raise HTTPException(503, "Chưa có dữ liệu demo. Chạy bộ nạp LANL trước.") from error
    except Exception as error:
        logger.exception("Không đọc được dữ liệu baseline")
        raise HTTPException(503, "Không đọc được dữ liệu baseline. Kiểm tra backend hoặc Neo4j.") from error
