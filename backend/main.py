from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ChatRequest(BaseModel):
    message : str

@app.post("/chat")
def chat(request : ChatRequest):
    message = request.message

    try: 
        n = int(message)
        result = 2 ** n
        response = str(result)

    except ValueError:
        response = "Không biết"

    return {
        "reply": response
    }
    

