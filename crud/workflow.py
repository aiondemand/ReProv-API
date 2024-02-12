import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Body
from db.workflow import Workflow, WorkflowModel
from db.user import User
from db.init_db  import session
# from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.exc import IntegrityError, InvalidRequestError, DBAPIError

from reana_client.api import client
import tempfile

router = APIRouter()

@router.get("/")
async def get_all_workflows(skip: int = 0, limit: int = 10):
    workflows = session.query(Workflow.id,Workflow.name,Workflow.version,Workflow.reana_id,Workflow.reana_name).offset(skip).limit(limit).all()
    return workflows


@router.get("/{workflow_id}")
async def get_workflow_by_id(id: int):
    workflow = session.query(Workflow.id,Workflow.name,Workflow.version,Workflow.reana_id,Workflow.reana_name).filter(Workflow.id == id).first()

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {id} not found",
        )

    return workflow


@router.post("/register/")
async def register_workflow(workflow: WorkflowModel = Depends(), spec_file: UploadFile = File(...), input_file: UploadFile = File(None)):
    spec_file_content = spec_file.file.read()
    input_file_content = input_file.file.read() if input_file else None
    try:
        db_workflow = Workflow(name=workflow.name, version=workflow.version, spec_file=spec_file_content, input_file = input_file_content)
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
            "New Workflow registered with":{
                "ID": db_workflow.id,
                "Name : Version": f"{workflow.name} : {workflow.version}",
            } 
        }
 


@router.post(
        "/execute/",
)

async def execute_workflow(name:str = None, version: str = None):
    if name is None and version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Name and version must be provided in order to execute a workflow",
        )

    workflow = session.query(Workflow).filter(
            Workflow.name == name
                    and
            Workflow.version == version
    ).first()


    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {name}:{version} was not found",
        )
    
    with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.cwl',delete=False) as spec_temp_file:
        spec_temp_file.write(workflow.spec_file)
    
    if workflow.input_file:
        with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.yaml',delete=False) as input_temp_file:
            input_temp_file.write(workflow.input_file)
        with open(os.path.join(os.getcwd(),input_temp_file.name)) as f:
            for line in f:
                k, v = line.strip().split(": ")
                inputs["parameters"][k] = v
    
    inputs = {"parameters":{}}
    try:
        reana_workflow = client.create_workflow_from_json(
            name=f"{name}:{version}",
            access_token=os.environ['REANA_ACCESS_TOKEN'],
            workflow_file=os.path.join(os.getcwd(),spec_temp_file.name),
            parameters = inputs if inputs["parameters"] != {} else None,
            workflow_engine='cwl'
        )
        workflow.reana_id = reana_workflow['workflow_id']
        workflow.reana_name = reana_workflow['workflow_name']
        session.commit()
        session.refresh(workflow)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem while creating REANA workflow: " + str(e),
        )
    try:
        workflow_run = client.start_workflow(
            workflow=workflow.reana_name, 
            access_token= os.environ['REANA_ACCESS_TOKEN'],
            parameters = {}
        )
        print(workflow_run)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem while starting REANA workflow: " + str(e),
        )

    finally:
        os.remove(os.path.join(os.getcwd(),spec_temp_file.name))
        if workflow.input_file:
            os.remove(os.path.join(os.getcwd(),input_temp_file.name))
        return {
            "New Workflow started":{
                "ID": workflow.id,
                "Name": workflow.name,
                "Version": workflow.version,
                "Run Number": workflow_run['run_number'],
                "REANA ID": workflow.reana_id
            
            } 
        }

@router.put("/update/")
async def update_workflow(id: int, name:str = None, version: str = None, spec_file: UploadFile = File(None), input_file: UploadFile = File(None)):

    fields_to_update = {
        k: v for k, v in {
            'name': name,
            'version': version,
            'spec_file': spec_file.file.read() if spec_file else None,
            'input_file': input_file.file.read() if input_file else None
        }.items() if v is not None}

    wf_updated = session.query(Workflow).filter(Workflow.id == id).update(fields_to_update)
    if wf_updated == 0:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not update workflow with ID: {id}"
        )

    session.commit()
    return {
            "Workflow Updated":{
            "ID": id,
            "Name": name,
            "Version": version
       } 
    }
 


@router.delete("/{id}", response_model=dict)
async def delete_workflow(id: int):
    workflow = session.query(Workflow).filter(Workflow.id == id).first()

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {id} not found",
        )

    session.delete(workflow)
    session.commit()

    return {"message": f"Workflow with ID {id} has been deleted"}