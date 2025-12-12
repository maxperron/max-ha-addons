from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from database import create_db_and_tables
from routers import users, accounts, categories, transactions, imports, trips

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    yield
    # Shutdown

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ... imports ...

app = FastAPI(lifespan=lifespan)

app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(imports.router)
app.include_router(trips.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    # Ingress in Home Assistant usually forwards to the container on the ingress_port.
    # We bind to 0.0.0.0 to be accessible from outside the container.
    uvicorn.run(app, host="0.0.0.0", port=8000)
