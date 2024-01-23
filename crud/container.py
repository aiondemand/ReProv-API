from fastapi import APIRouter, Depends, HTTPException, status,File, UploadFile, Form
from typing import Optional
from db.container import Container, ContainerModel
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import tempfile
import os
import docker

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

def build_docker_image(dockerfile_content: str) -> str:
    client = docker.from_env()

    # Create a temporary file for the Dockerfile content
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_dockerfile:
        temp_dockerfile.write(dockerfile_content)

    try:
        # Build Docker image
        image, logs = client.images.build(path=".", dockerfile=temp_dockerfile.name, tag="my_image")
    finally:
        # Cleanup: Remove the temporary Dockerfile
        temp_dockerfile.close()
        os.remove(temp_dockerfile.name)

    # Return image URL
    return "my_image"


@router.post("/upload/")
async def upload_container(container: ContainerModel = Depends(), dockerfile: UploadFile = File(None)):    
    try:
        if (not container.url or not container.tag) and not dockerfile:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You must provide url:tag OR Dockerfile"
            )     
        if container.url and container.name and dockerfile:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You must either provide url:tag OR Dockerfile but not both"
            ) 
        if dockerfile and not (container.url or container.tag):
            file_content = dockerfile.file.read().decode("utf-8")
            build_docker_image(file_content)
     
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