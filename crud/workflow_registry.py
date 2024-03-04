from utils.response import Response
from fastapi import APIRouter, UploadFile, File, Depends
from db.workflow_registry import WorkflowRegistry, WorkflowRegistryModel
from db.init_db import session
from sqlalchemy.exc import IntegrityError
from utils.wrap_cwl import wrap
from ruamel.yaml import YAML

router = APIRouter()


@router.get(
    "/",
    description="List all workflows in the registry",
)
async def list_workflows(skip: int = 0, limit: int = 10):
    yaml = YAML(typ='safe', pure=True)
    workflows = session.query(WorkflowRegistry).offset(skip).limit(limit).all()
    data = [
        {
            'registry_id': w.id,
            'name': w.name,
            'version': w.version,
            'spec_file_content': yaml.load(w.spec_file_content.decode('utf-8')),
            'input_file_content': w.input_file_content,
        } for w in workflows
    ]
    return Response(
        success=True,
        message='Workflows successfully retrieved',
        data=data
    )


@router.get(
    "/{registry_id}",
    description="Get details of a specific workflow in the registry by its ID.",
)
async def get_workflow_details(registry_id: int):
    yaml = YAML(typ='safe', pure=True)
    workflow = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == registry_id).first()

    if workflow is None:
        return Response(
            success=False,
            message="Invalid registry_id",
            error_code=404,
            data={}
        )
    data = {
        'registry_id': workflow.id,
        'name': workflow.name,
        'version': workflow.version,
        'spec_file_content': yaml.load(workflow.spec_file_content.decode('utf-8')),
        'input_file_content': workflow.input_file_content,
    }
    return Response(
        success=True,
        message="Workflow was successfully retrieved",
        data=data
    )


@router.post(
    "/register/",
    description="Register a new workflow in the registry, providing metadata and configuration details for execution",

)
async def register_workflow(workflow: WorkflowRegistryModel = Depends(), spec_file: UploadFile = File(...), input_file: UploadFile = File(None)):
    spec_file_content = wrap(spec_file.file.read())
    input_file_content = input_file.file.read() if input_file else None

    workflow = WorkflowRegistry(name=workflow.name, version=workflow.version, spec_file_content=spec_file_content, input_file_content=input_file_content)
    try:
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
    except IntegrityError:
        session.rollback()
        return Response(
            success=False,
            message="Integrity error. Duplicate name and version combination.",
            error_code=400,
            data={}
        )
    finally:
        data = {
            'registry_id': workflow.id,
            'name': workflow.name,
            'version': workflow.version
        }
        return Response(
            success=True,
            message="New Workflow was successfully registered",
            data=data
        )


@router.put(
    "/update/{registry_id}",
    description="Modify an existing workflow's metadata, configuration, or steps to adapt to changing requirements.",
)
async def update_workflow(registry_id: int, name: str = None, version: str = None, spec_file: UploadFile = File(None), input_file: UploadFile = File(None)):
    fields_to_update = {
        k: v for k, v in {
            'name': name,
            'version': version,
            'spec_file_content': spec_file.file.read() if spec_file else None,
            'input_file_content': input_file.file.read() if input_file else None
        }.items() if v is not None}

    wf_updated = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == registry_id).update(fields_to_update)
    if wf_updated == 0:
        return Response(
            success=True,
            message="No workflows were updated",
            data={}
        )

    session.commit()
    data = {
        'registry_id': registry_id
    }
    return Response(
        success=True,
        message="Workflow was succesfully updated",
        data=data
    )


@router.delete(
    "/delete/{registry_id}",
    description="Remove a workflow from the registry, making it unavailable for execution.",
)
async def delete_workflow(registry_id: int):
    workflow = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == registry_id).first()
    if workflow is None:
        return Response(
            success=False,
            message="Invalid registry_id",
            error_code=404,
            data={}
        )

    session.delete(workflow)
    session.commit()

    data = {
        'registry_id': registry_id
    }
    return Response(
        success=True,
        message="Workflow has been deleted",
        data=data
    )
