from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backoffice_agent import router as backoffice_router


app = FastAPI(title="One-Person Back Office", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backoffice_router)


@app.get("/")
def health():
    return {"status": "ok", "app": "One-Person Back Office"}
