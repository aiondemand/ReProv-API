from fastapi import FastAPI
from db.init_db import engine, Base
from db.init_db import Base
from db import container,workflow_registry
from crud.container import router as container_router
from crud.workflow_registry import router as workflow_registry_router
from crud.workflow_execution import router as workflow_execution_router
from crud.user import router as user_router

def create_tables():
    Base.metadata.create_all(bind=engine)
        
def create_routers(app):
    app.include_router(container_router, prefix="/container", tags=["container"])
    app.include_router(workflow_registry_router, prefix="/workflow_registry", tags=["workflow_registry"])
    app.include_router(workflow_execution_router, prefix="/workflow_execution", tags=["workflow_execution"])
    app.include_router(user_router, prefix="/user", tags=["user"])

def start_application():
    app = FastAPI(title='Provenance API')
    create_tables()
    create_routers(app)
    return app


app = start_application()


@app.get("/")
def home():
    return {}