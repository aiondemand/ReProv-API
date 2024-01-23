from fastapi import APIRouter, Depends, HTTPException, status
from db.user import User, UserModel
from db.init_db  import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter()



@router.post("/add/")
async def add_user(user: UserModel):    
    try:
        db_user = User(**user.dict())
        session.add(db_user)
        session.commit()
        return {
                    "User": UserModel.from_orm(db_user)
                }
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Integrity error. Username already exists."
        ) from e
        

@router.put("/update/")
async def update_user(username: str, updated_user: UserModel):
    existing_user = session.query(User).filter(User.username == username).first()

    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with username {username} not found",
        )

    for key, value in updated_user.dict().items():
        setattr(existing_user, key, value)

    session.commit()
    session.refresh(existing_user)
    return existing_user
 

@router.delete("/{user_id}", response_model=dict)
async def delete_user(username: str):
    user = session.query(User).filter(User.username == username).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with username {username} not found",
        )

    session.delete(user)
    session.commit()

    return {"message": f"User with username {username} has been deleted"}