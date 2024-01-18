from fastapi import FastAPI
from db.session import engine 
from db.models import *

def create_tables():  
    Base.metadata.create_all(bind=engine)
        
def start_application():
    app = FastAPI(title='Provenance API')
    create_tables()
    return app


app = start_application()


@app.get("/")
def home():
    return {}