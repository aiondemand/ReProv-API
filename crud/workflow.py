import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from db.workflow import Workflow, WorkflowModel
from db.user import User
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from reana_client.api import client
import tempfile

router = APIRouter()

@router.get("/test")
async def test():
    out = client.ping(access_token=os.environ['REANA_ACCESS_TOKEN'])
    print(out)


@router.get("/", response_model=list[WorkflowModel])
async def get_all_workflows(skip: int = 0, limit: int = 10):
    workflows = session.query(Workflow).offset(skip).limit(limit).all()
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowModel)
async def get_workflow_by_id(workflow_id: int):
    workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found",
        )

    return workflow


@router.post("/register/")
async def register_workflow(workflow: WorkflowModel = Depends(), spec_file: UploadFile = File(...), input_file: UploadFile = File(None)):
    spec_file_content = spec_file.file.read()
    input_file_content = input_file.file.read() if input_file else None
    with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.cwl',delete=False) as spec_temp_file:
        spec_temp_file.write(spec_file_content)

    try:
       
        reana_workflow = client.create_workflow_from_json(
                name=workflow.name,
                access_token=os.environ['REANA_ACCESS_TOKEN'],
                workflow_file=os.path.join(os.getcwd(),spec_temp_file.name),
                workflow_engine='cwl'
            )
        
        db_workflow = Workflow(name=workflow.name, version=workflow.version, reana_id=reana_workflow['workflow_id'], reana_name=reana_workflow['workflow_name'], spec_file=spec_file_content, input_file = input_file_content)
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
        os.remove(os.path.join(os.getcwd(),spec_temp_file.name))
        return {
            "New Workflow registered with":{
                "ID": db_workflow.id,
                "Name / Version": f"{workflow.name} / {workflow.version}",
                "Reana ID": reana_workflow['workflow_id'],
                "Reana Name": reana_workflow['workflow_name'],
            } 
        }
 

@router.post("/execute/")
async def execute_workflow(user_id: str, workflow_id: int):
    workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found",
    )

    user = session.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
    )


    return {}



@router.put("/update/")
async def update_workflow(workflow_id: int, updated_workflow: WorkflowModel):
    existing_workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()

    if existing_workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found",
        )

    for key, value in updated_workflow.dict().items():
        setattr(existing_workflow, key, value)

    session.commit()
    session.refresh(existing_workflow)
    return existing_workflow
 


@router.delete("/{workflow_id}", response_model=dict)
async def delete_workflow(workflow_id: int):
    workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found",
        )

    session.delete(workflow)
    session.commit()

    return {"message": f"Workflow with ID {workflow_id} has been deleted"}