from fastapi import APIRouter, Depends, HTTPException, status
from db.container import Container, ContainerModel
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/", response_model=list[ContainerModel])
async def get_all_containers(skip: int = 0, limit: int = 10):
    containers = session.query(Container).offset(skip).limit(limit).all()
    return containers

@router.get("/{container_id}", response_model=ContainerModel)
async def get_container_by_id(container_id: int):
    container = session.query(Container).filter(Container.id == container_id).first()

    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container with ID {container_id} not found",
        )

    return container


@router.post("/upload/")
async def upload_container(container: ContainerModel):    
    try:
        db_container = Container(**container.dict())
        session.add(db_container)
        session.commit()
        return {
                    "container": ContainerModel.from_orm(db_container)
                }
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Integrity error. Duplicate URL and tag combination."
        ) from e
        

@router.put("/update/")
async def update_container(container_id: int, updated_container: ContainerModel):
    existing_container = session.query(Container).filter(Container.id == container_id).first()

    if existing_container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container with ID {container_id} not found",
        )

    for key, value in updated_container.dict().items():
        setattr(existing_container, key, value)

    session.commit()

    session.refresh(existing_container)

    return existing_container
 


@router.delete("/{container_id}", response_model=dict)
async def delete_container(container_id: int):
    container = session.query(Container).filter(Container.id == container_id).first()

    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container with ID {container_id} not found",
        )

    session.delete(container)
    session.commit()

    return {"message": f"Container with ID {container_id} has been deleted"}