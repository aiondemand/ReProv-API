from fastapi import FastAPI
from db.init_db import engine, Base
from db.init_db import Base
from db import container,workflow
from crud.container import router as container_router


def create_tables():
    Base.metadata.create_all(bind=engine)
        
def create_routers(app):
    app.include_router(container_router, prefix="/container", tags=["container"])


def start_application():
    app = FastAPI(title='Provenance API')
    create_tables()
    create_routers(app)
    return app


app = start_application()


@app.get("/")
def home():
    return {}