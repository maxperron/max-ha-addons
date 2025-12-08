from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World from Family Expenses Tracker Web UI!"}

if __name__ == "__main__":
    # Ingress in Home Assistant usually forwards to the container on the ingress_port.
    # We bind to 0.0.0.0 to be accessible from outside the container.
    uvicorn.run(app, host="0.0.0.0", port=8000)
