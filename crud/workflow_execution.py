import asyncio
import os
from fastapi import APIRouter,HTTPException, BackgroundTasks, status
from fastapi_utils.tasks import repeat_every
from db.workflow_execution import WorkflowExecution
from db.workflow_registry import WorkflowRegistry
from db.user import User
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from reana_client.api import client
import tempfile
from datetime import datetime
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


router = APIRouter()

@router.get(
        "/",
        description="List all workflows that were executed",
)
async def list_executed_workflows():
    workflows = session.query(WorkflowExecution).all()
    executed_workflows = client.get_workflows(
        access_token=os.environ['REANA_ACCESS_TOKEN'],
        type='batch',
        verbose=True
    )

    executed_workflows = []
    for w in workflows:
        executed_workflows.append(
            client.get_workflows(
                access_token=os.environ['REANA_ACCESS_TOKEN'],
                type='batch',
                verbose=True,
                workflow=w.reana_id
            )[0]
        )
    print(len(executed_workflows))
    return executed_workflows

@router.get(
        "/{registry_id}",
        description="Get details of a specific workflow that was executed by its ID.",
)
async def get_workflow_by_id(registry_id: int):
    workflows = session.query(WorkflowExecution).filter(WorkflowExecution.registry_id == registry_id).all()
    if workflows == []:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID: {registry_id} was not executed in the past",
        )
    
    executed_workflows = []
    for w in workflows:
        executed_workflows.append(
            client.get_workflows(
                access_token=os.environ['REANA_ACCESS_TOKEN'],
                type='batch',
                verbose=True,
                workflow=w.reana_id
            )[0]
        )
    return executed_workflows





@router.post(
        "/execute/{registry_id}",
        description="Execute workflow by invoking REANA system"
)
async def execute_workflow(registry_id: int, background_tasks: BackgroundTasks):
    workflow_registry = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == registry_id).first()

    if workflow_registry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID: {registry_id} was not found",
        )
    
    with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.cwl',delete=False) as spec_temp_file:
        spec_temp_file.write(workflow_registry.spec_file_content)
    
    if workflow_registry.input_file_content:
        with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.yaml',delete=False) as input_temp_file:
            input_temp_file.write(workflow_registry.input_file_content)
        with open(os.path.join(os.getcwd(),input_temp_file.name)) as f:
            for line in f:
                k, v = line.strip().split(": ")
                inputs["parameters"][k] = v
    
    inputs = {"parameters":{}}
    try:
        reana_workflow = client.create_workflow_from_json(
            name=f"{workflow_registry.name}:{workflow_registry.version}",
            access_token=os.environ['REANA_ACCESS_TOKEN'],
            workflow_file=os.path.join(os.getcwd(),spec_temp_file.name),
            parameters = inputs if inputs["parameters"] != {} else None,
            workflow_engine='cwl'
        )
    except Exception as e:
        os.remove(os.path.join(os.getcwd(),spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(),input_temp_file.name))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem while creating REANA workflow: " + str(e),
        )
    try:

        workflow_run = client.start_workflow(
            workflow=reana_workflow['workflow_name'],
            access_token= os.environ['REANA_ACCESS_TOKEN'],
            parameters = {}
        )
        workflow_execution = WorkflowExecution(
            registry_id=registry_id,
            reana_id=workflow_run['workflow_id'],
            reana_name=workflow_run['workflow_name'],
            reana_run_number=workflow_run['run_number'],
        )
        background_tasks.add_task(monitor_execution, workflow_execution.reana_id)
        session.add(workflow_execution)
        session.commit()
        session.refresh(workflow_execution)
        print(workflow_run)
    except Exception as e:
        os.remove(os.path.join(os.getcwd(),spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(),input_temp_file.name))

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem while starting REANA workflow: " + str(e),
        )

    finally:
        os.remove(os.path.join(os.getcwd(),spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(),input_temp_file.name))
        return {
            "New Workflow started":{
                "ID": workflow_execution.id,
                "Name": workflow_registry.name,
                "Version": workflow_registry.version,
                "REANA Name": workflow_execution.reana_name,
                "REANA ID": workflow_execution.reana_id,
                "Run Number": workflow_execution.reana_run_number,
            } 
        }
   
 
async def monitor_execution(reana_id):
    while True:
        await asyncio.sleep(2) 
        status = client.get_workflow_status(
            workflow=reana_id,
            access_token=os.environ['REANA_ACCESS_TOKEN']
        )['status']

        if status == 'finished' or status == 'failed':
            break

    workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.reana_id == reana_id).first()
    workflow_execution.end_time = datetime.utcnow()
    workflow_execution.status = status
    session.commit()



@router.delete(
        "/delete/{registry_id}",
        description="Delete workflow from execution history"
)
async def delete_workflow(id: int):
    pass