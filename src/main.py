from fastapi import FastAPI
from schema.init_db import engine, Base
from crud.workflow_registry import router as workflow_registry_router
from crud.workflow_execution import router as workflow_execution_router
from crud.prov import router as prov_router
from crud.image_registry import router as image_registry_router


def create_tables():
    Base.metadata.create_all(bind=engine)


def create_routers(app):
    app.include_router(
        workflow_registry_router,
        prefix="/workflow_registry",
        tags=["Workflow Registry"]
    )
    app.include_router(
        workflow_execution_router,
        prefix="/workflow_execution",
        tags=["Workflow Execution"]
    )
    app.include_router(
        prov_router,
        prefix="/provenance",
        tags=["Provenance"]
    )
    app.include_router(
        image_registry_router,
        prefix="/image_registry",
        tags=["Image Registry"]
    )


def start_application():
    app = FastAPI(
        title='Provenance API',
        # swagger_ui_parameters={"defaultModelsExpandDepth": -1}
    )
    create_tables()
    create_routers(app)
    return app


app = start_application()
