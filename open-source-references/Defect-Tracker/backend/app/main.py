from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.defects import router as defects
from app.db.session import engine
from app.db.base import Base
from app.api.routes import auth
from app.api.routes import safety
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    print("Starting up...")
    yield
    print("Shutting down...")

app = FastAPI(title="Defect Tracker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Defect Tracker API!"}

@app.get("/health")
def health_check():
    return {"status": "db ok"}

app.include_router(defects, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(safety.router, prefix="/api")


