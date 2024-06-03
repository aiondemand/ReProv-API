import os
import pandas as pd
from datetime import datetime
from prov.model import ProvDocument
from prov.dot import prov_to_dot
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse
from fastapi import APIRouter, Depends
from schema.prov import Entity, Activity, Agent
from schema.init_db import session
from schema.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from schema.workflow_registry import WorkflowRegistry
from authentication.auth import authenticate_user
from models.user import User
from ruamel.yaml import YAML
from reana_client.api import client
from models.response import Response
from sqlalchemy.exc import SQLAlchemyError
import json

router = APIRouter()


@router.get(
    "/capture/{execution_id}",
    description="Capture provenance for workflow with specific execution_id",
)
async def track_provenance(
    execution_id: int,
    user: User = Depends(authenticate_user)
):
    try:
        workflow_execution = session.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid execution_id",
            error_code=404,
            data={}
        )

    execution_status = workflow_execution.status
    if execution_status != 'finished':
        return Response(
            success=False,
            message="Workflow must be finished in order to capture provenance",
            error_code=409,
            data={}
        )

    try:
        previously_captured = session.query(Activity).filter(Activity.workflow_execution_id == workflow_execution.id).first()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )
    
    if previously_captured:
        return Response(
            success=False,
            message="Provenance was captured before",
            error_code=403,
            data={}
        )

    try:
        workflow_spec_file = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == workflow_execution.registry_id).first().spec_file_content
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    yaml = YAML(typ='safe', pure=True)
    spec_file_yaml = yaml.load(workflow_spec_file)
    
    try:
        workflow_execution_steps = session.query(WorkflowExecutionStep).filter(WorkflowExecutionStep.workflow_execution_id == workflow_execution.id).all()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    workflow_files = client.list_files(
        workflow=workflow_execution.reana_id,
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )
    map_file_content = client.download_file(
        workflow=workflow_execution.reana_id,
        access_token=os.environ['REANA_ACCESS_TOKEN'],
        file_name='outputs/map.txt'
    )[0].decode('utf-8').split('\n')

    input_file_content = json.loads(
        client.download_file(
            workflow=workflow_execution.reana_id,
            access_token=os.environ['REANA_ACCESS_TOKEN'],
            file_name='inputs.json'
        )[0].decode('utf-8')
    )

    map_df = pd.DataFrame([line.split(',') for line in map_file_content if line], columns=['filename', 'entity_name'])

    intermediate_files = [f for f in workflow_files if f['name'].startswith('cwl/') and f['name'].split('/')[-1] in map_df['entity_name'].values]
    output_files = [f for f in workflow_files if f['name'].startswith('outputs/') and f['name'].split('/')[-1] != 'map.txt']
    spec_file = [f for f in workflow_files if f['name'] == 'workflow.json'][0]

    external_files = [f for f in workflow_files if f not in intermediate_files + output_files + [spec_file] and f['name'].split('/')[-1] != 'map.txt']

    # create entity for the whole workflow
    workflow_entity = Entity(
        type='workflow',
        path=f"{workflow_execution.reana_id}/workflow.json",
        name='workflow',
        size=spec_file['size']['human_readable'],
        last_modified=datetime.fromisoformat(spec_file['last-modified']),
        workflow_execution_id=workflow_execution.id
    )

    # create entities for the intermediate files
    intermediate_entities = [
        Entity(
            type='workflow_intermediate_result_file',
            path=i_file['name'],
            name=i_file['name'].split('/')[-1].replace(':', '_'),
            size=i_file['size']['human_readable'],
            last_modified=datetime.fromisoformat(i_file['last-modified']),
            workflow_execution_id=workflow_execution.id
        ) for i_file in intermediate_files
    ]

    # create entities for the final output files
    output_entities = [
        Entity(
            type='workflow_final_result_file',
            path=o_file['name'],
            name=o_file['name'].split('/')[-1].replace(':', '_'),
            size=o_file['size']['human_readable'],
            last_modified=datetime.fromisoformat(o_file['last-modified']),
            workflow_execution_id=workflow_execution.id
        ) for o_file in output_files
    ]

    external_entities = [
        Entity(
            type='external_file',
            path=e_file['name'],
            name=e_file['name'].split('/')[-1].replace(':', '_'),
            size=e_file['size']['human_readable'],
            last_modified=datetime.fromisoformat(e_file['last-modified']),
            workflow_execution_id=workflow_execution.id
        ) for e_file in external_files
    ]

    entities = [workflow_entity] + intermediate_entities + output_entities + external_entities

    step_activities = [
        Activity(
            type='step_execution',
            name=s.name.replace(':', '_'),
            start_time=s.start_time,
            end_time=s.end_time,
            workflow_execution_id=workflow_execution.id
        ) for s in workflow_execution_steps if s.name != 'map'
    ]
    workflow_activity = Activity(
        type='workflow_execution',
        name=f"{workflow_execution.reana_name.replace(':','_')}_{workflow_execution.reana_run_number}",
        start_time=workflow_execution.start_time,
        end_time=workflow_execution.end_time,
        workflow_execution_id=workflow_execution.id
    )
    activities = [workflow_activity] + step_activities

    try:
        for e in entities:
            session.add(e)
        for a in activities:
            session.add(a)
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    for s in spec_file_yaml['steps']:
        if s == 'map':  # ignore map step
            continue

        step_file_inputs = [key for key, value in spec_file_yaml['steps'][s]['run']['inputs'].items() if value == 'File']
        step_file_outputs = [o['id'] for o in spec_file_yaml['steps'][s]['run']['outputs'] if o['type'] == 'File']

        # for each input file in step (f):
        # this file wasUsedBy the corresponding entity (entity_name) with filename=map_df.loc['filename'=f]
        for f in step_file_inputs:
            # check if is external file
            external_input = False
            for i in spec_file_yaml['inputs']:
                if 'valueFromPlatform' in i:
                    for key, value in input_file_content.items():
                        if key == f:
                            entity = [e for e in external_entities if e.name == value['path']][0]
                            external_input = True

            if not external_input:
                f_in = spec_file_yaml['steps'][s]['in'][f].split('/')
                if len(f_in) == 1:
                    entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
                    entity = [e for e in entities if e.name == entity_name][0]
                else:
                    id = f_in[1]
                    entity_name = map_df.loc[map_df['filename'] == id].to_dict('records')[0]['entity_name']
                    entity = [e for e in entities if e.name == entity_name][0]
 
            activity = [a for a in step_activities if a.name == s][0]
            activity.used.append(entity)
            try:
                session.add(activity)
            except SQLAlchemyError as e:
                session.rollback()
                return Response(
                    success=False,
                    message=f"Database error: {str(e)}",
                    error_code=500,
                    data={}
                )

        for f in step_file_outputs:
            entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
            entity = [e for e in entities if e.name == entity_name][0]
            activity = [a for a in step_activities if a.name == s][0]

            activity.generated.append(entity)
            try:
                session.add(activity)
            except SQLAlchemyError as e:
                session.rollback()
                return Response(
                    success=False,
                    message=f"Database error: {str(e)}",
                    error_code=500,
                    data={}
                )

    for e in output_entities:
        workflow_activity.generated.append(e)
        try:
            session.add(workflow_activity)
        except SQLAlchemyError as e:
            session.rollback()
            return Response(
                success=False,
                message=f"Database error: {str(e)}",
                error_code=500,
                data={}
            )

    try:
        session.add(workflow_entity)
        agent = Agent(
            type='person',
            name=workflow_execution.username,
            workflow_execution_id=workflow_execution.id
        )
        session.add(agent)

        software = Agent(
            type='software',
            name='software executing experiments',
            workflow_execution_id=workflow_execution.id
        )
        session.add(software)

        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    return Response(
        success=True,
        message='Provenance retrieved successfully',
        data={}
    )


@router.get(
    "/draw/{execution_id}",
    description="Create a graphical representation of provenance for workflow with specific execution id",
)
async def draw_provenance(
    execution_id: int,
    user: User = Depends(authenticate_user)
):
    try:
        workflow_execution = session.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid execution_id",
            error_code=404,
            data={}
        )

    try:
        activities = session.query(Activity).filter(
            Activity.workflow_execution_id == workflow_execution.id
        ).all()

        workflow_entity = session.query(Entity).filter(
            Entity.workflow_execution_id == workflow_execution.id,
            Entity.type == 'workflow'
        ).first()

        workflow_activity = session.query(Activity).filter(
            Activity.workflow_execution_id == workflow_execution.id,
            Activity.type == 'workflow_execution'
        ).first()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    doc = ProvDocument()
    doc.set_default_namespace('https://www.w3.org/TR/prov-dm/')

    # sort activities based on end time
    sorted_activities = sorted(activities, key=lambda x: x.end_time)
    for i, a in enumerate(sorted_activities, start=1):
        doc.activity(
            a.name.replace(':', '_'),
            a.start_time,
            a.end_time,
            {
                'id': a.id,
                'type': a.type,
                'series': i
            }
        )

    doc.entity(
        workflow_entity.name,
        {
            'id': workflow_entity.id,
            'type': workflow_entity.type,
            'path': workflow_entity.path,
            'name': workflow_entity.name,
            'size': workflow_entity.size,
            'last_modified': workflow_entity.last_modified,
        }
    )

    for a in activities:
        for entity in a.used:
            doc.entity(
                entity.name,
                {
                    'id': entity.id,
                    'type': entity.type,
                    'path': entity.path,
                    'name': entity.name,
                    'size': entity.size,
                    'last_modified': entity.last_modified,
                }
            )

            doc.used(a.name, entity.name)

        for entity in a.generated:
            doc.entity(
                entity.name,
                {
                    'id': entity.id,
                    'type': entity.type,
                    'path': entity.path,
                    'name': entity.name,
                    'size': entity.size,
                    'last_modified': entity.last_modified,
                }
            )
            doc.generation(entity.name, a.name)

    doc.start(
        activity=sorted_activities[0].name,
        trigger=workflow_entity.name,
        other_attributes={
            'time': sorted_activities[0].start_time
        }
    )

    doc.end(
        activity=sorted_activities[-1].name,
        trigger=workflow_entity.name,
        other_attributes={
            'time': sorted_activities[-1].end_time
        }
    )

    try:
        person = session.query(Agent).filter(
            Agent.workflow_execution_id == workflow_execution.id,
            Agent.type == 'person'
        ).first()

        software = session.query(Agent).filter(
            Agent.workflow_execution_id == workflow_execution.id,
            Agent.type == 'software'
        ).first()
    except SQLAlchemyError as e:
        session.rollback()
        return Response(
            success=False,
            message=f"Database error: {str(e)}",
            error_code=500,
            data={}
        )

    doc.agent(
        person.name,
        {
            'type': 'person'
        }
    )

    doc.agent(
        software.name,
        {
            'type': 'software'
        }
    )

    doc.actedOnBehalfOf(
        delegate=software.name,
        responsible=person.name
    )
    doc.attribution(
        entity=workflow_entity.name,
        agent=software.name
    )

    doc.association(
        agent=software.name,
        activity=workflow_activity.name
    )

    png_name = f"{workflow_execution.reana_name}:{workflow_execution.reana_run_number}-provenance.png"
    prov_to_dot(doc).write_png(png_name)

    def _delete_png_file():
        os.unlink(png_name)

    return FileResponse(
        png_name,
        filename=png_name,
        background=BackgroundTask(_delete_png_file),
    )
