import os
import pandas as pd
from datetime import datetime
from prov.model import ProvDocument
from prov.dot import prov_to_dot
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse
from fastapi import APIRouter
from db.prov import Entity, Activity, EntityUsedBy, EntityGeneratedBy
from db.init_db import session
from db.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from db.workflow_registry import WorkflowRegistry
from ruamel.yaml import YAML
from reana_client.api import client
from utils.response import Response

router = APIRouter()


@router.get(
    "/capture/",
    description="Capture provenance for workflow with specific name & run number",
)
async def track_provenance(reana_name: str, run_number: int):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name,
        WorkflowExecution.reana_run_number == run_number
    ).first()
    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid reana_name and reana_number combination",
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

    previously_captured = session.query(Activity).filter(Activity.workflow_execution_id == workflow_execution.id).first()
    if previously_captured:
        return Response(
            success=False,
            message="Provenance was captured before",
            error_code=403,
            data={}
        )

    workflow_execution_steps = session.query(WorkflowExecutionStep).filter(WorkflowExecutionStep.workflow_execution_id == workflow_execution.id).all()

    workflow_files = client.list_files(
        workflow=workflow_execution.reana_id,
        access_token=os.environ['REANA_ACCESS_TOKEN']
    )
    output_files = [f for f in workflow_files if f['name'].startswith('outputs/') and f['name'].split('/')[-1] != 'map.txt']
    intermediate_files = [f for f in workflow_files if f['name'].startswith('cwl/')]
    spec_file = [f for f in workflow_files if f['name'] == 'workflow.json'][0]
    map_file_content = client.download_file(
        workflow=workflow_execution.reana_id,
        access_token=os.environ['REANA_ACCESS_TOKEN'],
        file_name='outputs/map.txt'
    )[0].decode('utf-8').split('\n')

    map_df = pd.DataFrame([line.split(',') for line in map_file_content if line], columns=['filename', 'entity_name'])

    # create entity for the whole workflow
    workflow_entity = Entity(
        type='workflow',
        path=f"/var/reana/users/00000000-0000-0000-0000-000000000000/workflows/{workflow_execution.reana_id}/workflow.json",
        name='workflow.json',
        size=spec_file['size']['human_readable'],
        last_modified=datetime.fromisoformat(spec_file['last-modified'])
    )

    # create entities for the intermediate files
    intermediate_entities = [
        Entity(
            type='workflow_intermediate_result_file',
            path=i_file['name'],
            name=i_file['name'].split('/')[-1],
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
            name=o_file['name'].split('/')[-1],
            size=o_file['size']['human_readable'],
            last_modified=datetime.fromisoformat(o_file['last-modified']),
            workflow_execution_id=workflow_execution.id
        ) for o_file in output_files
    ]

    entities = [workflow_entity] + intermediate_entities + output_entities

    step_activities = [
        Activity(
            type='step_execution',
            name=s.name,
            start_time=s.start_time,
            end_time=s.end_time,
            workflow_execution_id=workflow_execution.id
        ) for s in workflow_execution_steps if s.name != 'map'
    ]
    workflow_activity = Activity(
        type='workflow_execution',
        name=f"{workflow_execution.reana_name}.{workflow_execution.reana_run_number}",
        start_time=workflow_execution.start_time,
        end_time=workflow_execution.end_time,
        workflow_execution_id=workflow_execution.id
    )
    activities = [workflow_activity] + step_activities

    for e in entities:
        session.add(e)
    for a in activities:
        session.add(a)

    workflow_spec_file = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == workflow_execution.registry_id).first().spec_file_content
    yaml = YAML(typ='safe', pure=True)
    data = yaml.load(workflow_spec_file)
    for s in data['steps']:
        if s == 'map':  # ignore map step
            continue

        step_file_inputs = [key for key, value in data['steps'][s]['run']['inputs'].items() if value == 'File']
        step_file_outputs = [o['id'] for o in data['steps'][s]['run']['outputs'] if o['type'] == 'File']

        # for each input file in step (f):
        # this file wasUsedBy the corresponding entity (eneity_name) with filename=map_df.loc['filename'=f]

        for f in step_file_inputs:
            entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
            entity = [e for e in entities if e.name == entity_name][0]
            activity = [a for a in step_activities if a.name == s][0]
            activity.used.append(entity)
            session.add(activity)

        for f in step_file_outputs:
            entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
            entity = [e for e in entities if e.name == entity_name][0]
            activity = [a for a in step_activities if a.name == s][0]

            activity.generated.append(entity)
            session.add(activity)

    for e in entities:
        # workflow used every entity
        workflow_activity.used.append(e)
        # workflow generated every entity that was not input on first step
        workflow_activity.generated.append(e)
        session.add(workflow_activity)

    workflow_entity.started.append(workflow_activity)
    workflow_entity.ended.append(workflow_activity)

    session.commit()
    return Response(
        success=True,
        message='Provenance retrieved successfully',
        data={}
    )


@router.get(
    "/draw/",
    description="Create a graphical represenation of provenance for workflow with specific reana_name and run number",
)
async def draw_provenance(reana_name: str, run_number: int):
    workflow_execution = session.query(WorkflowExecution).filter(
        WorkflowExecution.reana_name == reana_name,
        WorkflowExecution.reana_run_number == run_number
    ).first()
    if workflow_execution is None:
        return Response(
            success=False,
            message="Invalid reana_name and reana_number combination",
            error_code=404,
            data={}
        )
    activities = session.query(Activity).filter(
        Activity.workflow_execution_id == workflow_execution.id
    ).all()
    entities = session.query(Entity).filter(
        Entity.workflow_execution_id == workflow_execution.id
    ).all()

    doc = ProvDocument()
    doc.set_default_namespace('https://www.w3.org/TR/prov-dm/')

    for e in entities:
        doc.entity(
            e.name,
            {
                'id': e.id,
                'type': e.type,
                'path': e.path,
                'name': e.name,
                'size': e.size,
                'last_modified': e.last_modified,
            }
        )

    for a in activities:
        doc.activity(
            a.name.replace(':', '_'),
            a.start_time,
            a.end_time,
            {
                'id': a.id,
                'type': a.type
            }
        )

    for e in entities:
        generated_by = session.query(EntityGeneratedBy).filter(EntityGeneratedBy.entity_id == e.id).all()
        for g in generated_by:
            entity_name = session.query(Entity.name).filter(Entity.id == g.entity_id).first()[0].replace(':', '_')
            activity_name = session.query(Activity.name).filter(Activity.id == g.activity_id).first()[0].replace(':', '_')
            doc.wasGeneratedBy(entity_name, activity_name)

        used_by = session.query(EntityUsedBy).filter(EntityUsedBy.entity_id == e.id).all()
        for u in used_by:
            entity_name = session.query(Entity.name).filter(Entity.id == u.entity_id).first()[0].replace(':', '_')
            activity_name = session.query(Activity.name).filter(Activity.id == u.activity_id).first()[0].replace(':', '_')
            doc.used(entity_name, activity_name)

    png_name = f"{reana_name}:{run_number}-provenance.png"
    prov_to_dot(doc).write_png(png_name)

    def _delete_png_file():
        os.unlink(png_name)

    return FileResponse(
        png_name,
        filename=png_name,
        background=BackgroundTask(_delete_png_file),
    )
