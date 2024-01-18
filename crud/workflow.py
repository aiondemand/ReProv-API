from fastapi import APIRouter, Depends, HTTPException, status
from db.workflow import Workflow, WorkflowModel
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter()

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


@router.post("/upload/")
async def upload_workflow(workflow: WorkflowModel):    
    try:
        db_workflow = Workflow(**workflow.dict())
        session.add(db_workflow)
        session.commit()
        return {
                    "Workflow": WorkflowModel.from_orm(db_workflow)
                }
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Integrity error. Duplicate URL and tag combination."
        ) from e
        

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