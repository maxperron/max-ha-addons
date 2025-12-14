from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from database import create_db_and_tables
from routers import users, accounts, categories, transactions, imports, trips, settings, stats

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("--------------------------------------------------")
    print("   FAMILY EXPENSES TRACKER - VERSION v0.9.11")
    print("--------------------------------------------------")
    create_db_and_tables()
    yield
    # Shutdown

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ... imports ...

app = FastAPI(title="Family Expenses Tracker")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(imports.router)
app.include_router(trips.router)
app.include_router(settings.router)
app.include_router(stats.router)

@app.get("/")
def read_root():
    response = FileResponse('static/index.html')
    # Prevent aggressive caching of the main page
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    # Ingress in Home Assistant usually forwards to the container on the ingress_port.
    # We bind to 0.0.0.0 to be accessible from outside the container.
    uvicorn.run(app, host="0.0.0.0", port=8000)
