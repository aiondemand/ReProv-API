from fastapi import APIRouter, Depends
from authentication.auth import authenticate_user

router = APIRouter()


@router.get(
    "/",
    description="Test Authentication of Provenance API",
)
async def test_authentication(auth_dict=Depends(authenticate_user)):
    print(auth_dict)
    return {}
