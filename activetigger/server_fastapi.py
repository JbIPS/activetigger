from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Body, Form
import logging
from typing import Annotated
from datamodels import ParamsModel, ElementModel, NextModel
from project_fastapi import Server, Project

logging.basicConfig(filename='log.log', 
                    encoding='utf-8', 
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')



# à terme toute demande de l'app aura les informations de la connexion
# nom de l'utilisateur
# accès autoris
# projet connecté
# Passer l'utilisateur en cookie lors de la connexion ?  https://www.tutorialspoint.com/fastapi/fastapi_cookie_parameters.htm
# unwrapping pydandic object  UserInDB(**user_dict)
# untiliser l'héritage de class & le filtrage


#######
# API #
#######
    
server = Server()
app = FastAPI()

# ------------
# Dependencies
# ------------

async def get_project(project_name: str) -> ParamsModel:
    """
    Fetch existing project associated with the request
    """

    # If project doesn't exist
    if not server.exists(project_name):
        raise HTTPException(status_code=404, detail="Project not found")

    # If the project exist
    if project_name in server.projects:
        # If already loaded
        return server.projects[project_name]
    else:
        # To load
        server.start_project(project_name)
        return server.projects[project_name]

# TODO : gérer l'authentification de l'utilisateur
async def verified_user(x_token: Annotated[str, Header()]):
    # Cookie ou header ?
    if False:
        raise HTTPException(status_code=400, detail="Invalid user")

# ------
# Routes
# ------

@app.get("/project/{name_project}")
async def info_projects(name_project:str = "all"):
    """
    Get informations about projects
    """
    if name_project == "all":
        return {"informations":"all"}

    return {"informations":name_project}


async def get_params(project_name:str = Form(),
                     col_text:str = Form("text"),
                     n_rows:int = Form(2000),
                     col_tags:str = Form(None),
                     embeddings:list = Form([])) -> ParamsModel:
    """
    Collect form data to project params
    """
    p = ParamsModel(project_name=project_name,
                    col_text = col_text,
                    n_rows=n_rows,
                    col_tags=col_tags,
                    embeddings=embeddings)
    return p

@app.post("/project/new", dependencies=[Depends(verified_user)])
async def new_project(project: Annotated[ParamsModel, Depends(get_params)],
                      file: UploadFile = File(),
                      ) -> ParamsModel:

    """
    Load new project
    Parameters:
        file (file)
        n_rows (int)
    """

    # For the moment, only csv
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=422, 
                detail="Only CSV file for the moment")
        
    # Test if project exist
    if server.exists(project.project_name):
        raise HTTPException(status_code=422, 
                detail="Project already exist")

    project = server.create_project(project, file)

    return project
    #return {"success":"project created"}

@app.get("/e/{id}", dependencies=[Depends(verified_user)])
async def get_element(id:str, 
                      project: Annotated[Project, Depends(get_project)],
                      response_model=ElementModel) -> ElementModel:
    """
    Get specific element
    """
    try:
        e = ElementModel(**project.get_element(id))
        return e
    except: # gérer la bonne erreur
        raise HTTPException(status_code=404, detail="Element not found")

@app.get("/next", dependencies=[Depends(verified_user)])
async def get_next(project: Annotated[Project, Depends(get_project)],
                   scheme:str,
                   mode:str = "deterministic",
                   on:str = "untagged"): #-> ElementModel:
    """
    Get next element
    """
    e = project.get_next(scheme = scheme,
                         mode = mode,
                         on = on)
    
    return {"r":e}





"""

    def get_next(self,
                 scheme:str,
                 mode:str = "deterministic",
                 on:str = "untagged",
                 tag:None|str = None) -> dict:

mode:str|None = None, 
               on:str|None = None, 
               scheme:str|None = None

        if req["type"] == "next" :
            req = p.get_next(mode = req["content"]["mode"]["mode"], 
                             on = req["content"]["mode"]["on"],
                             scheme = req["content"]["scheme"]["current"])
            return req
"""