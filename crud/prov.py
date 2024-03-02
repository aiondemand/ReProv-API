import os
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from db.prov import Entity, Activity
from db.init_db  import session
from db.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from db.workflow_registry import WorkflowRegistry
from ruamel.yaml import YAML
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from reana_client.api import client

router = APIRouter()



@router.get(
	"/capture/",
	description="Capture provenance for workflow with specific reana_name and run number",
)
async def track_provenance(reana_name: str, run_number:int):
	workflow_execution = session.query(WorkflowExecution).filter(WorkflowExecution.reana_name == reana_name, WorkflowExecution.reana_run_number == run_number).first()
	workflow_execution_steps = session.query(WorkflowExecutionStep).filter(WorkflowExecutionStep.workflow_execution_id == workflow_execution.id).all()

	if workflow_execution is None:
		raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with name {reana_name} and run number {run_number} was not found",
        )
	
	execution_status = workflow_execution.status

	if execution_status != 'finished':
		raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with name {reana_name} and run number {run_number} must be finished in order to capture provenance",
        )


	workflow_files = client.list_files(
		workflow=workflow_execution.reana_id,
		access_token=os.environ['REANA_ACCESS_TOKEN']
	)
	output_files = [f for f in workflow_files if f['name'].startswith('outputs/') and f['name'].split('/')[-1] != 'map.txt' ]
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
			last_modified=datetime.fromisoformat(i_file['last-modified'])
		) for i_file in intermediate_files
	]
	

	# create entities for the final output files
	output_entities = [
		Entity(
			type='workflow_final_result_file',
			path=o_file['name'],
			name=o_file['name'].split('/')[-1],
			size=o_file['size']['human_readable'],
			last_modified=datetime.fromisoformat(o_file['last-modified'])
		) for o_file in output_files
	]
	
	entities = [workflow_entity] + intermediate_entities + output_entities

	activities = [
		Activity(
			type='step_execution',
			name=s.name,
			start_time=s.start_time,
			end_time=s.end_time
		) for s in workflow_execution_steps if s.name != 'map'
	]

	for e in entities:
		session.add(e)
	for a in activities:
		session.add(a)

	session.commit()


	workflow_spec_file = session.query(WorkflowRegistry).filter(WorkflowRegistry.id == workflow_execution.registry_id).first().spec_file_content
	yaml = YAML(typ='safe', pure=True)
	data = yaml.load(workflow_spec_file)
	for s in data['steps'] :
		if s == 'map': # ignore map step
			continue

		step_file_inputs = [key for key, value in data['steps'][s]['run']['inputs'].items() if value == 'File']
		step_file_outputs =[o['id'] for o in data['steps'][s]['run']['outputs'] if o['type'] == 'File']

		# for each input file in step (f):
		# this file wasUsedBy the corresponding entity (eneity_name) with filename=map_df.loc['filename'=f]

		for f in step_file_inputs:
			entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
			entity = [e for e in entities if e.name==entity_name][0]
			activity = [a for a in activities if a.name==s][0]
			activity.used.append(entity)
			session.add(activity)

		
		for f in step_file_outputs:
			entity_name = map_df.loc[map_df['filename'] == f].to_dict('records')[0]['entity_name']
			entity = [e for e in entities if e.name==entity_name][0]
			activity = [a for a in activities if a.name==s][0]

			activity.generated.append(entity)
			session.add(activity)
	
	session.commit()

	return {}