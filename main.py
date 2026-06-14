from fastapi import FastAPI

app = FastAPI(title="DevOps Lab API", version="1.0.0")
@app.get("/")
def root():
    return {"message": "Welcome to the DevOps Lab", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}