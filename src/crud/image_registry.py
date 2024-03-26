from models.user import User
from fastapi import APIRouter, UploadFile, File, Depends
from authentication.auth import authenticate_user

router = APIRouter()


@router.get(
    "/",
    description="List all images the registry that belong to the same group as the authenticated user."
)
async def list_images(
    user: User = Depends(authenticate_user)
):
    pass


@router.get(
    "/register/",
    description="Register a new image in the platform"
)
async def register_image(
    name: str,
    version: str,
    description: str,
    image: UploadFile = File(...),
    user: User = Depends(authenticate_user)
):
    pass
