import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from db.workflow_registry import WorkflowRegistry, WorkflowRegistryModel
from db.user import User
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from utils.wrap_cwl import wrap
from reana_client.api import client
import tempfile
from ruamel.yaml import YAML

router = APIRouter()

@router.get(
        "/",
        description="List all workflows in the registry",
)
async def list_workflows(skip: int = 0, limit: int = 10):
    yaml = YAML(typ='safe', pure=True)
    workflows = session.query(WorkflowRegistry).offset(skip).limit(limit).all()
    return [
        {
            'id': w.id,
            'name': w.name,
            'version': w.version,
            'spec_file_content': yaml.load(w.spec_file_content.decode('utf-8')),
            'input_file_content': w.input_file_content,
        }  for w in workflows
    ]
        



@router.get(
        "/{id}",
        description="Get details of a specific workflow in the registry by its ID.",
)
async def get_workflow_details(id: int):
    yaml = YAML(typ='safe', pure=True)
    workflow = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == id).first()

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {id} was not found in the registry",
        )
    return {
        'id': workflow.id,
        'name': workflow.name,
        'version': workflow.version,
        'spec_file_content': yaml.load(workflow.spec_file_content.decode('utf-8')),
        'input_file_content': workflow.input_file_content,
    }

@router.post(
        "/register/",
        description="Register a new workflow in the registry, providing metadata and configuration details for execution",

)
async def register_workflow(workflow: WorkflowRegistryModel = Depends(), spec_file: UploadFile = File(...), input_file: UploadFile = File(None)):
    spec_file_content = wrap(spec_file.file.read())
    input_file_content = input_file.file.read() if input_file else None
    
    db_workflow = WorkflowRegistry(name=workflow.name, version=workflow.version, spec_file_content=spec_file_content, input_file_content = input_file_content)
    try:
        session.add(db_workflow)
        session.commit()
        session.refresh(db_workflow)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Integrity error. Duplicate name and version combination."
        ) from e
    finally:
        return {
            "New Workflow registered successfully with":{
                "ID": db_workflow.id,
                "Name:Version": f"{workflow.name}:{workflow.version}",
            } 
        }

@router.put(
        "/update/{id}",
        description="Modify an existing workflow's metadata, configuration, or steps to adapt to changing requirements.",
)
async def update_workflow(id: int, name:str = None, version: str = None, spec_file: UploadFile = File(None), input_file: UploadFile = File(None)):
    fields_to_update = {
        k: v for k, v in {
            'name': name,
            'version': version,
            'spec_file_content': spec_file.file.read() if spec_file else None,
            'input_file_content': input_file.file.read() if input_file else None
        }.items() if v is not None}

    wf_updated = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == id).update(fields_to_update)
    if wf_updated == 0:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not update workflow with ID: {id}"
        )

    session.commit()
    return {
            "Workflow updated successfully":{
                "ID": id,
       } 
    }
 
@router.delete(
        "/delete/{id}",
        description="Remove a workflow from the registry, making it unavailable for execution.",
)
async def delete_workflow(id: int):
    workflow = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == id).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {id} not found",
        )

    session.delete(workflow)
    session.commit()

    return {"message": f"Workflow with ID {id} has been deleted"}
