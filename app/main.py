from fastapi import FastAPI
from schema.init_db import engine, Base
from crud.workflow_registry import router as workflow_registry_router
from crud.workflow_execution import router as workflow_execution_router
from crud.prov import router as prov_router
from crud.auth import router as auth_router


def create_tables():
    Base.metadata.create_all(bind=engine)


def create_routers(app):
    app.include_router(
        workflow_registry_router,
        prefix="/workflow_registry",
        tags=["workflow_registry"]
    )
    app.include_router(
        workflow_execution_router,
        prefix="/workflow_execution",
        tags=["workflow_execution"]
    )
    app.include_router(
        prov_router, 
        prefix="/provenance", 
        tags=["provenance"]
    )
    app.include_router(
        auth_router, 
        prefix="/auth", 
        tags=["auth"]
    )


def start_application():
    app = FastAPI(title='Provenance API')
    create_tables()
    create_routers(app)
    return app


app = start_application()


@app.get("/")
def home():
    return {}
