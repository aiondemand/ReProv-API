import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from db.prov import Entity
from db.init_db  import session
from db.workflow_execution import WorkflowExecution
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
	output_files = [f for f in workflow_files if f['name'].startswith('outputs/')]
	intermediate_files = [f for f in workflow_files if f['name'].startswith('cwl/')]
	spec_file = [f for f in workflow_files if f['name'] == 'workflow.json'][0]


	# create entity for the whole workflow
	workflow_entity = Entity(
		type='workflow',
		path=f"/var/reana/users/00000000-0000-0000-0000-000000000000/workflows/{workflow_execution.reana_id}/workflow.json",
		name='workflow.json',
		size=spec_file['size']['human_readable'],
		last_modified=spec_file['last-modified']
	)
	session.add(workflow_entity)

	# create entities for the intermediate files
	intermediate_entities = [
		Entity(
			type='workflow_intermediate_result_file',
			path=i_file['name'],
			name=i_file['name'].split('/')[-1],
			size=i_file['size']['human_readable'],
			last_modified=i_file['last-modified']
		) for i_file in intermediate_files
	]
	for i_entity in intermediate_entities:
		session.add(i_entity)


	# create entities for the final output files
	output_entities = [
		Entity(
			type='workflow_final_result_file',
			path=o_file['name'],
			name=o_file['name'].split('/')[-1],
			size=o_file['size']['human_readable'],
			last_modified=o_file['last-modified']
		) for o_file in output_files
	]
	for o_entity in output_entities:
		session.add(o_entity)


	return {}