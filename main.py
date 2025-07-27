from fastapi import FastAPI
from routes import projects

app = FastAPI()
app.include_router(projects.router)
