import asyncio
import os
import zipfile
from fastapi.responses import FileResponse
from fastapi import APIRouter,HTTPException, BackgroundTasks, status
from fastapi_utils.tasks import repeat_every
from db.workflow_execution import WorkflowExecution, WorkflowExecutionStep
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
        description="List all workflows that have been executed",
)
async def list_executed_workflows():
    workflow_executions = session.query(WorkflowExecution).all()
    if workflow_executions is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workflows have been executed",
        )
    
    for workflow_execution in workflow_executions:
        data = {
            'id': workflow_execution.id,
            'start_time': workflow_execution.start_time,
            'end_time': workflow_execution.end_time,
            'status': workflow_execution.status,
            'reana_name': workflow_execution.reana_name,
            'reana_run_number': workflow_execution.reana_run_number,
            'registry_id': workflow_execution.registry_id,
            'steps' : [] 
        }
        workflow_execution_steps = session.query(WorkflowExecutionStep).filter(WorkflowExecutionStep.workflow_execution_id == workflow_execution.id).all()
        for step in workflow_execution_steps:
            data['steps'].append(
                {
                    'id': step.id,
                    'name': step.name,
                    'status': step.status,
                    'start_time': step.start_time,
                    'end_time': step.end_time
                }
            )
    return data

@router.get(
        "/{execution_id}",
        description="Get details of a specific workflow that was executed by its execution ID.",
)
async def get_workflow_by_id(execution_id: int):
    workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.id==execution_id).first()
    if workflow_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow execution with ID:{execution_id} was not found",
        )
    
    data = {
        'id': workflow_execution.id,
        'start_time': workflow_execution.start_time,
        'end_time': workflow_execution.end_time,
        'status': workflow_execution.status,
        'reana_name': workflow_execution.reana_name,
        'reana_run_number': workflow_execution.reana_run_number,
        'registry_id': workflow_execution.registry_id,
        'steps' : [] 
    }
    workflow_execution_steps = session.query(WorkflowExecutionStep).filter(WorkflowExecutionStep.workflow_execution_id == workflow_execution.id).all()
    for step in workflow_execution_steps:
        data['steps'].append(
            {
                'id': step.id,
                'name': step.name,
                'status': step.status,
                'start_time': step.start_time,
                'end_time': step.end_time
            }
        )
    return data

    
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
    
    inputs = {"parameters":{}}
    if workflow_registry.input_file_content:
        with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.yaml',delete=False) as input_temp_file:
            input_temp_file.write(workflow_registry.input_file_content)
        with open(os.path.join(os.getcwd(),input_temp_file.name)) as f:
            for line in f:
                k, v = line.strip().split(": ")
                inputs["parameters"][k] = v
    
   
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
    workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.reana_id == reana_id).first()
    prev_step = None
    while True:
        workflow_status = client.get_workflow_status(
            workflow=reana_id,
            access_token=os.environ['REANA_ACCESS_TOKEN']
        )

        current_step = workflow_status['progress']['current_step_name']
        if current_step != prev_step: # if a new step is running: 
            if prev_step is not None:
                prev_workflow_execution_step = session.query(WorkflowExecutionStep).filter(
                    WorkflowExecutionStep.workflow_execution_id == workflow_execution.id,
                    WorkflowExecutionStep.name == prev_step,
                ).first()
                prev_workflow_execution_step.end_time = datetime.utcnow()
                prev_workflow_execution_step.status = 'finished'
                session.add(prev_workflow_execution_step)
                session.commit()    
            
            current_workflow_execution_step = WorkflowExecutionStep(
                name=current_step,
                workflow_execution_id=workflow_execution.id
            )

            prev_step = current_step

            session.add(current_workflow_execution_step)
            session.commit()
      
        if workflow_status['status'] != workflow_execution.status:
            workflow_execution.status = workflow_status['status']
        if workflow_status['status'] == 'finished' or workflow_status['status'] == 'failed':
            break

        await asyncio.sleep(0.1)

    last_workflow_execution_step = session.query(WorkflowExecutionStep).filter(
                    WorkflowExecutionStep.workflow_execution_id == workflow_execution.id,
                    WorkflowExecutionStep.name == current_step,
    ).first()
    last_workflow_execution_step.end_time = datetime.utcnow()
    session.add(last_workflow_execution_step)
    session.commit()

    workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.reana_id == reana_id).first()
    workflow_execution.end_time = datetime.utcnow()
    session.add(workflow_execution)
    session.commit()



@router.delete(
        "/delete/",
        description="Delete every workflow execution that was associated with a registry ID OR with a name provided by the execution system "
)
async def delete_workflow_execution(registry_id: int = None, reana_name: str = None):
    if registry_id and reana_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Either provide registry_id OR name but not both"
        )
    deleted_workflows_id = []
    if registry_id:
        workflows = session.query(WorkflowExecution).filter(WorkflowExecution.registry_id == registry_id).all()
    else:
        workflows = session.query(WorkflowExecution).filter(WorkflowExecution.reana_name == reana_name).all()

    for w in workflows:
        try:
            deleted_workflows_id.append(
                client.delete_workflow(
                    workflow=w.reana_id if registry_id else reana_name,
                    access_token=os.environ['REANA_ACCESS_TOKEN'],
                    all_runs=True,
                    workspace=True
                )['workflow_id']
            )
            session.delete(w)
            session.commit()
        except Exception as e:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem while deleting REANA workflow: " + str(e),
        )
    
    if registry_id:
        message = f"Every workflow associated with registry_id:{registry_id} was successfully deleted"
    else:
        message = f"Every workflow associated with name:{reana_name} was successfully deleted"
    return {
            "Message": message,
            "Workflow executions deleted": deleted_workflows_id                
        }

from starlette.background import BackgroundTask


@router.get(
        "/outputs/",
        description="Download outputs of an executed workflow",
)
async def download_outputs(reana_name: str, run_number:int):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name, WorkflowExecution.reana_run_number == run_number
    ).first()

    if workflow_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with name: {reana_name} and run number: {run_number} was not found"
        )

    (output_content,file_name, is_zipped) = client.download_file(
        workflow=workflow_execution.reana_id,
        file_name='outputs',
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )
    def _delete_tmp_file():
        os.unlink(temp_file.name)

    with tempfile.NamedTemporaryFile(dir=os.getcwd(), delete=False) as temp_file:
        temp_file.write(output_content)

        return FileResponse(
            temp_file.name, 
            filename='outputs.zip',
            background=BackgroundTask(_delete_tmp_file),
        )



@router.get(
        "/inputs/",
        description="Download inputs of an executed workflow",
)
async def download_inputs(reana_name: str, run_number:int):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name, WorkflowExecution.reana_run_number == run_number
    ).first()

    if workflow_execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with name: {reana_name} and run number: {run_number} was not found"
        )
    (input_content,file_name, _) = client.download_file(
        workflow=workflow_execution.reana_id,
        file_name='inputs.json',
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )
    def _delete_tmp_file():
        os.unlink(temp_file.name)

    if input_content == b'{}':
          raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Input file was not found (default values were used)"
        )

    with tempfile.NamedTemporaryFile(dir=os.getcwd(), delete=False) as temp_file:
        temp_file.write(input_content)

        return FileResponse(
            temp_file.name, 
            filename=file_name,
            background=BackgroundTask(_delete_tmp_file),
        )

