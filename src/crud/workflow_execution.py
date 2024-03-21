import asyncio
import os
from fastapi.responses import FileResponse
from fastapi import APIRouter, BackgroundTasks, Depends
from starlette.background import BackgroundTask
from schema.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from schema.workflow_registry import WorkflowRegistry
from schema.init_db import session
from authentication.auth import authenticate_user
from models.user import User
from utils.cwl import add_mapping_step, replace_placeholders
from reana_client.api import client
import tempfile
from datetime import datetime
import urllib3
from models.response import Response
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


router = APIRouter()


@router.get(
    "/",
    description="List all workflows that have been executed",
)
async def list_executed_workflows(
    user: User = Depends(authenticate_user)
):
    workflow_executions = session.query(WorkflowExecution).filter(
        WorkflowExecution.group == user.group
    ).all()
    data = {}
    for workflow_execution in workflow_executions:
        workflow_data = {
            'username': user.username,
            'group': user.group,
            'execution_id': workflow_execution.id,
            'start_time': workflow_execution.start_time,
            'end_time': workflow_execution.end_time,
            'status': workflow_execution.status,
            'reana_name': workflow_execution.reana_name,
            'reana_run_number': workflow_execution.reana_run_number,
            'registry_id': workflow_execution.registry_id,
            'steps': []
        }
        workflow_execution_steps = session.query(WorkflowExecutionStep).filter(
            WorkflowExecutionStep.workflow_execution_id == workflow_execution.id
        ).all()
        for step in workflow_execution_steps:
            workflow_data['steps'].append(
                {
                    'step_id': step.id,
                    'name': step.name,
                    'status': step.status,
                    'start_time': step.start_time,
                    'end_time': step.end_time
                }
            )
        name = f"{workflow_execution.reana_name}:{workflow_execution.reana_run_number}"
        data[name] = workflow_data
    return Response(
        success=True,
        message='Workflow executions retrieved successfully',
        data=data
    )


@router.get(
    "/{execution_id}",
    description="Get details of a specific workflow that was executed by its execution ID.",
)
async def get_workflow_execution_by_id(
    execution_id: int,
    user: User = Depends(authenticate_user)
):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.id == execution_id,
        WorkflowExecution.group == user.group
    ).first()
    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid execution_id",
            error_code=404,
            data={}
        )
    data = {
        'username': user.username,
        'group': user.group,
        'execution_id': workflow_execution.id,
        'start_time': workflow_execution.start_time,
        'end_time': workflow_execution.end_time,
        'status': workflow_execution.status,
        'reana_name': workflow_execution.reana_name,
        'reana_run_number': workflow_execution.reana_run_number,
        'registry_id': workflow_execution.registry_id,
        'steps': []
    }
    workflow_execution_steps = session.query(WorkflowExecutionStep).filter(
        WorkflowExecutionStep.workflow_execution_id == workflow_execution.id
    ).all()
    for step in workflow_execution_steps:
        data['steps'].append(
            {
                'step_id': step.id,
                'name': step.name,
                'status': step.status,
                'start_time': step.start_time,
                'end_time': step.end_time
            }
        )
    return {
        "success": True,
        "message": "Workflow execution successfully retrieved",
        "data": data
    }


@router.post(
    "/execute/{registry_id}",
    description="Execute workflow by invoking REANA system"
)
async def execute_workflow(
    registry_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(authenticate_user)
):
    workflow_registry = session.query(WorkflowRegistry).filter(
        WorkflowRegistry.id == registry_id,
        WorkflowRegistry.group == user.group
    ).first()

    if workflow_registry is None:
        return Response(
            success=False,
            message="Invalid registry_id",
            error_code=404,
            data={}
        )

    with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.cwl', delete=False) as spec_temp_file:

        spec_file_with_mapping_step = add_mapping_step(workflow_registry.spec_file_content.encode('utf-8'))
        spec_file_without_placeholders, needed_entities = replace_placeholders(spec_file_with_mapping_step)
        if spec_file_without_placeholders is None and needed_entities is None:
            return Response(
                success=False,
                message="Invalid entity id in placeholder",
                error_code=404,
                data={}
            )

        spec_temp_file.write(spec_file_without_placeholders)

    inputs = {"parameters": {}}
    if workflow_registry.input_file_content:
        with tempfile.NamedTemporaryFile(dir=os.getcwd(), suffix='.yaml', delete=False) as input_temp_file:
            input_temp_file.write(workflow_registry.input_file_content.encode('utf-8'))
        with open(os.path.join(os.getcwd(), input_temp_file.name)) as f:
            for line in f:
                k, v = line.strip().split(": ")
                inputs["parameters"][k] = v

    for entity in needed_entities:
        inputs['parameters'][entity['id']] = {
            'class': 'File',
            'path': entity['data'].name
        }

    try:
        reana_workflow = client.create_workflow_from_json(
            name=f"{workflow_registry.name}:{workflow_registry.version}",
            access_token=os.environ['REANA_ACCESS_TOKEN'],
            workflow_file=os.path.join(os.getcwd(), spec_temp_file.name),
            parameters=inputs,
            workflow_engine='cwl'
        )

    except Exception as e:
        os.remove(os.path.join(os.getcwd(), spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(), input_temp_file.name))
        return Response(
            success=False,
            message="Problem while creating REANA workflow: " + str(e),
            error_code=503,
            data={}
        )

    try:
        for entity in needed_entities:
            prev_execution = session.query(WorkflowExecution.reana_id).filter(WorkflowExecution.id == entity['data'].workflow_execution_id).first()
            file_name = entity['data'].path
            downloaded_entity = client.download_file(
                workflow=prev_execution.reana_id,
                file_name=file_name,
                access_token=os.environ['REANA_ACCESS_TOKEN'],
            )

            client.upload_file(
                workflow=reana_workflow['workflow_id'],
                file_=downloaded_entity[0],
                file_name=entity['data'].name,
                access_token=os.environ['REANA_ACCESS_TOKEN']
            )

        workflow_run = client.start_workflow(
            workflow=reana_workflow['workflow_id'],
            access_token=os.environ['REANA_ACCESS_TOKEN'],
            parameters={}
        )
        workflow_execution = WorkflowExecution(
            username=user.username,
            group=user.group,
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
        os.remove(os.path.join(os.getcwd(), spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(), input_temp_file.name))
            return Response(
                success=False,
                message="Problem while starting REANA workflow: " + str(e),
                error_code=503,
                data={}
            )

    finally:
        os.remove(os.path.join(os.getcwd(), spec_temp_file.name))
        if workflow_registry.input_file_content:
            os.remove(os.path.join(os.getcwd(), input_temp_file.name))
        data = {
            "username": user.username,
            "group": user.group,
            "execution_id": workflow_execution.id,
            "name": workflow_registry.name,
            "version": workflow_registry.version,
            "reana_name": workflow_execution.reana_name,
            "reana_id": workflow_execution.reana_id,
            "run_number": workflow_execution.reana_run_number,
        }
        return Response(
            success=True,
            message="New workflow started",
            data=data
        )


async def monitor_execution(reana_id):
    workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.reana_id == reana_id).first()
    prev_step = None
    while True:
        workflow_status = client.get_workflow_status(
            workflow=reana_id,
            access_token=os.environ['REANA_ACCESS_TOKEN']
        )

        current_step = workflow_status['progress']['current_step_name']
        if current_step != prev_step:  # if a new step is running:
            if prev_step is not None:
                prev_workflow_execution_step = session.query(WorkflowExecutionStep).filter(
                    WorkflowExecutionStep.workflow_execution_id == workflow_execution.id,
                    WorkflowExecutionStep.name == prev_step,
                ).first()
                prev_workflow_execution_step.end_time = datetime.utcnow()
                prev_workflow_execution_step.status = 'finished' if workflow_status['status'] != 'failed' else 'failed'
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

        await asyncio.sleep(0.001)

    final_status = client.get_workflow_status(
        workflow=reana_id,
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )

    last_workflow_execution_step = session.query(WorkflowExecutionStep).filter(
        WorkflowExecutionStep.workflow_execution_id == workflow_execution.id,
        WorkflowExecutionStep.name == current_step,
    ).first()

    if last_workflow_execution_step is not None:
        last_workflow_execution_step.end_time = datetime.utcnow()
        last_workflow_execution_step.status = final_status['status']
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
async def delete_workflow_execution(
    registry_id: int = None,
    reana_name: str = None,
    user: User = Depends(authenticate_user)
):
    if registry_id and reana_name:
        return Response(
            success=False,
            message="Either provide registry_id OR name but not both",
            error_code=403,
            data={}
        )

    deleted_workflows_id = []
    if registry_id:
        workflows = session.query(WorkflowExecution).filter(
            WorkflowExecution.registry_id == registry_id,
            WorkflowExecution.group == user.group
        ).all()
    else:
        workflows = session.query(WorkflowExecution).filter(
            WorkflowExecution.reana_name == reana_name,
            WorkflowExecution.group == user.group
        ).all()

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
            return Response(
                success=False,
                message="Problem while deleting REANA workflow: " + str(e),
                error_code=503,
                data={}
            )

    if registry_id:
        message = f"Every workflow associated with registry_id:{registry_id} was successfully deleted"
    else:
        message = f"Every workflow associated with name:{reana_name} was successfully deleted"
    data = deleted_workflows_id
    return Response(
        success=True,
        message=message,
        data=data
    )


@router.get(
    "/outputs/",
    description="Download outputs of an executed workflow",
)
async def download_outputs(
    reana_name: str,
    run_number: int,
    user: User = Depends(authenticate_user)
):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name,
        WorkflowExecution.reana_run_number == run_number,
        WorkflowExecution.group == user.group
    ).first()

    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid reana_name and reana_number combination",
            error_code=404,
            data={}
        )

    if workflow_execution.status != 'finished':
        return Response(
            success=False,
            message="Workflow must be finished in order to download output files",
            error_code=409,
            data={}
        )

    (output_content, file_name, is_zipped) = client.download_file(
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
async def download_inputs(
    reana_name: str,
    run_number: int,
    user: User = Depends(authenticate_user)
):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name,
        WorkflowExecution.reana_run_number == run_number,
        WorkflowExecution.group == user.group
    ).first()

    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid reana_name and reana_number combination",
            error_code=404,
            data={}
        )

    if workflow_execution.status != 'finished':
        return Response(
            success=False,
            message="Workflow must be finished in order to download input files",
            error_code=409,
            data={}
        )

    (input_content, file_name, _) = client.download_file(
        workflow=workflow_execution.reana_id,
        file_name='inputs.json',
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )

    def _delete_tmp_file():
        os.unlink(temp_file.name)

    if input_content == b'{}':
        return Response(
            success=True,
            message="Workflow does not have any input values (default were used)",
            data={}
        )

    with tempfile.NamedTemporaryFile(dir=os.getcwd(), delete=False) as temp_file:
        temp_file.write(input_content)

        return FileResponse(
            temp_file.name,
            filename=file_name,
            background=BackgroundTask(_delete_tmp_file),
        )
