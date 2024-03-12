from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Query, Form, Request
from fastapi.responses import FileResponse
import logging
from typing import Annotated, List
from datamodels import ProjectModel, ElementModel, TableElementsModel, Action, AnnotationModel, SchemeModel, Error, ProjectionModel
from datamodels import RegexModel, SimpleModelModel, BertModelModel
from server import Server, Project
import functions
from multiprocessing import Process
import time
import pandas as pd
import os
import concurrent.futures
import json

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

# middleware to update elements on events
async def update():
    """
    Function to be executed before each request
    """
    print(f"Updated Value at {time.strftime('%H:%M:%S')}")
    for p in server.projects:
        project = server.projects[p]

        # computing embeddings
        if (project.params.dir / "sbert.parquet").exists():
            df = pd.read_parquet(project.params.dir / "sbert.parquet") # load data TODO : bug potentiel lié à la temporalité
            project.features.add("sbert",df) # add to the feature manager
            if "sbert" in project.features.training:
                project.features.training.remove("sbert") # remove from pending processes
            os.remove(project.params.dir / "sbert.parquet") # clean the files
            logging.info("SBERT embeddings added to project") # log
        if (project.params.dir / "fasttext.parquet").exists():
            df = pd.read_parquet(project.params.dir / "fasttext.parquet")
            project.features.add("fasttext",df) 
            if "fasttext" in project.features.training:
                project.features.training.remove("fasttext") 
            os.remove(project.params.dir / "fasttext.parquet")
            print("Adding fasttext embeddings")
            logging.info("FASTTEXT embeddings added to project")
        
        # computing projection
        for u in project.features.available_projections:
            if ("future" in project.features.available_projections[u]):
                if project.features.available_projections[u]["future"].done():
                    df = project.features.available_projections[u]["future"].result()
                    project.features.available_projections[u]["data"] = df
                    del project.features.available_projections[u]["future"]
                    print("Adding projection data")

@app.middleware("http")
async def middleware(request: Request, call_next):
    """
    Middleware
    """
    await update()
    response = await call_next(request)
    return response

# ------------
# Dependencies
# ------------

async def get_project(project_name: str) -> ProjectModel:
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


# Projects management
#--------------------

@app.get("/state/{project_name}", dependencies=[Depends(verified_user)])
async def get_state(project: Annotated[Project, Depends(get_project)]):
    """
    Get state of a project
    TODO: a datamodel
    """
    r = project.get_state()
    return r

@app.get("/description", dependencies=[Depends(verified_user)])
async def get_description(project: Annotated[Project, Depends(get_project)],
                          scheme: str|None = None,
                          user:str|None = None):
    """
    Get description of a project / a specific scheme
    """
    r = project.get_description(scheme = scheme, user = user)
    return r

@app.get("/projects/{project_name}", dependencies=[Depends(verified_user)])
async def info_project(project_name:str|None = None):
    """
    Get info on project
    """
    return {project_name:server.db_get_project(project_name)}

@app.get("/projects", dependencies=[Depends(verified_user)])
async def info_all_projects():
    """
    Get all available projects
    """
    return {"existing projects":server.existing_projects()}

@app.post("/projects/new", dependencies=[Depends(verified_user)])
async def new_project(
                      file: Annotated[UploadFile, File()],
                      project_name:str = Form(),
                      user:str = Form(),
                      col_text:str = Form(),
                      col_id:str = Form(),
                      col_label:str = Form(None),
                      cols_context:List[str] = Form(None),
                      n_train:int = Form(),
                      n_test:int = Form(),
                      embeddings:list = Form(None),
                      n_skip:int = Form(None),
                      langage:str = Form(None),
                      ) -> ProjectModel|Error:
    """
    Load new project
        file (file)
        multiple parameters
    PAS LA SOLUTION LA PLUS JOLIE
    https://stackoverflow.com/questions/65504438/how-to-add-both-file-and-json-body-in-a-fastapi-post-request/70640522#70640522

    """

    # removing None parameters
    params_in = {
        "project_name":project_name,
        "user":user,         
        "col_text":col_text,
        "col_id":col_id,
        "n_train":n_train,
        "n_test":n_test,
        "embeddings":embeddings,
        "n_skip":n_skip,
        "langage":langage,
        "col_label":col_label,
        "cols_context":cols_context
        }
    params_out = params_in.copy()
    for i in params_in:
        if params_in[i] is None:
            del params_out[i]

    print(params_out)
    project = ProjectModel(**params_out)

    # For the moment, only csv
    if not file.filename.endswith('.csv'):
        return Error(error = "Only CSV file for the moment")
        
    # Test if project exist
    if server.exists(project.project_name):
        return Error(error = "Project already exist")

    project = server.create_project(project, file)

    return project

@app.post("/projects/delete", dependencies=[Depends(verified_user)])
async def delete_project(project_name:str):
    """
    Delete a project
    """
    r = server.delete_project(project_name)
    return r


# Annotation management
#--------------------

@app.get("/elements/next", dependencies=[Depends(verified_user)])
async def get_next(project: Annotated[Project, Depends(get_project)],
                   scheme:str,
                   selection:str = "deterministic",
                   sample:str = "untagged",
                   user:str = "user",
                   tag:str|None = None,
                   frame:list|None = None) -> ElementModel|Error:
    """
    Get next element
    """
    e = project.get_next(
                        scheme = scheme,
                        selection = selection,
                        sample = sample,
                        user = user,
                        tag = tag,
                        frame = frame
                        )
    if "error" in e:
        r = Error(**e)
    else:
        r = ElementModel(**e)
    return r


@app.get("/elements/projection/current", dependencies=[Depends(verified_user)])
async def get_projection(project: Annotated[Project, Depends(get_project)],
                         user:str):
    """
    Get projection data if computed
    """
    if user in project.features.available_projections:
        if not "data" in project.features.available_projections[user]:
            return {"status":"Still computing"}
        return {"data":project.features.available_projections[user]["data"].to_dict()}
    return {"error":"There is no projection available"}


@app.post("/elements/projection/compute", dependencies=[Depends(verified_user)])
async def compute_projection(project: Annotated[Project, Depends(get_project)],
                         user:str,
                         projection:ProjectionModel):
    """
    Start projection computation
    Dedicated process, end with a file on the project
    projection__user.parquet
    TODO : très moche comme manière de faire, à reprendre
    """
    if len(projection.features) == 0:
        return {"error":"No feature"}
    
    name = f"projection__{user}"
    features = project.features.get(projection.features)
    args = {
            "features":features,
            "params":projection.params
            }

    if projection.method == "umap":
        future_result = server.executor.submit(functions.compute_umap, **args)
        project.features.available_projections[user] = {
                                                        "params":projection,
                                                        "method":"umap",
                                                        "future":future_result
                                                        }
        return {"success":"Projection umap under computation"}
    if projection.method == "tsne":
        future_result = server.executor.submit(functions.compute_tsne, **args)
        project.features.available_projections[user] = {
                                                        "params":projection,
                                                        "method":"tsne",
                                                        "future":future_result
                                                        }
        return {"success":"Projection tsne under computation"}


    return {"error":"This projection is not available"}

@app.get("/elements/table", dependencies=[Depends(verified_user)])
async def get_list_elements(project: Annotated[Project, Depends(get_project)],
                            scheme:str,
                            min:int = 0,
                            max:int = 0,
                            mode:str = "all",
                        ):
    
    r = project.schemes.get_table(scheme, min, max, mode)
    return r.fillna("NA")
    
@app.post("/elements/table", dependencies=[Depends(verified_user)])
async def post_list_elements(project: Annotated[Project, Depends(get_project)],
                            user:str,
                            table:TableElementsModel
                            ):
    r = project.schemes.push_table(table = table, 
                                   user = user)
    return r


@app.get("/elements/stats", dependencies=[Depends(verified_user)])
async def get_stats(project: Annotated[Project, Depends(get_project)],
                    scheme:str,
                    user:str):
    r = project.get_stats_annotations(scheme, user)
    return r
    

@app.get("/elements/{element_id}", dependencies=[Depends(verified_user)])
async def get_element(element_id:str, 
                      project: Annotated[Project, Depends(get_project)]) -> ElementModel:
    """
    Get specific element
    """
    print(element_id)
    try:
        e = ElementModel(**project.get_element(element_id))
        return e
    except: # gérer la bonne erreur
        raise HTTPException(status_code=404, detail=f"Element {element_id} not found")
    

@app.post("/tags/{action}", dependencies=[Depends(verified_user)])
async def post_tag(action:Action,
                   project: Annotated[Project, Depends(get_project)],
                   annotation:AnnotationModel):
    """
    Add, Update, Delete annotations
    Comment : 
    - For the moment add == update
    """
    if action in ["add","update"]:
        if annotation.tag is None:
            raise HTTPException(status_code=422, 
                detail="Missing a tag")
        return project.schemes.push_tag(annotation.element_id, 
                                        annotation.tag, 
                                        annotation.scheme,
                                        annotation.user
                                        )
    if action == "delete":
        project.schemes.delete_tag(annotation.element_id, 
                                   annotation.scheme,
                                   annotation.user
                                   ) # add user deletion
        return {"success":"label deleted"}

# Schemes management
#-------------------


@app.get("/schemes", dependencies=[Depends(verified_user)])
async def get_schemes(project: Annotated[Project, Depends(get_project)],
                      scheme:str|None = None):
        """
        Available scheme of a project
        """
        if scheme is None:
            return project.schemes.get()
        a = project.schemes.available()
        if scheme in a:
            return {"scheme":a[scheme]}
        return {"error":"scheme not available"}


@app.post("/schemes/label/add", dependencies=[Depends(verified_user)])
async def add_label(project: Annotated[Project, Depends(get_project)],
                    scheme:str,
                    label:str,
                    user:str):
    """
    Add a label to a scheme
    """
    print(scheme, label, user)
    r = project.schemes.add_label(label, scheme, user)
    print(r)
    return r

@app.post("/schemes/label/delete", dependencies=[Depends(verified_user)])
async def delete_label(project: Annotated[Project, Depends(get_project)],
                    scheme:str,
                    label:str,
                    user:str):
    """
    Remove a label from a scheme
    """
    r = project.schemes.delete_label(label, scheme, user)
    return r


@app.post("/schemes/{action}", dependencies=[Depends(verified_user)])
async def post_schemes(
                        action:Action,
                        project: Annotated[Project, Depends(get_project)],
                        scheme:SchemeModel
                        ):
    """
    Add, Update or Delete scheme
    """
    if action == "add":
        r = project.schemes.add_scheme(scheme)
        return r
    if action == "delete":
        r = project.schemes.delete_scheme(scheme)
        return r
    if action == "update":
        r = project.schemes.update_scheme(scheme.name, scheme.tags, scheme.user)
        return r
    
    return {"error":"wrong route"}


# Features management
#--------------------

@app.get("/features", dependencies=[Depends(verified_user)])
async def get_features(project: Annotated[Project, Depends(get_project)]):
        """
        Available scheme of a project
        """
        return {"features":list(project.features.map.keys())}

@app.post("/features/add/regex", dependencies=[Depends(verified_user)])
async def post_regex(project: Annotated[Project, Depends(get_project)],
                          regex:RegexModel):
    r = project.add_regex(regex.name,regex.value)
    return r

@app.post("/features/add/{name}", dependencies=[Depends(verified_user)])
async def post_embeddings(project: Annotated[Project, Depends(get_project)],
                          name:str,
                          user:str):
    if name in project.features.training:
        return {"error":"This feature is already in training"}
    
    df = project.content[project.params.col_text]
    if name == "sbert":
        args = {
                "path":project.params.dir,
                "texts":df,
                "model":"distiluse-base-multilingual-cased-v1"
                }
        process = Process(target=functions.process_sbert, 
                          kwargs = args)
        process.start()
        project.features.training.append(name)
        return {"success":"computing sbert, it could take a few minutes"}
    if name == "fasttext":
        args = {
                "path":project.params.dir,
                "texts":df,
                "model":"/home/emilien/models/cc.fr.300.bin"
                }
        process = Process(target=functions.process_fasttext, 
                          kwargs = args)
        process.start()
        project.features.training.append(name)
        return {"success":"computing fasttext, it could take a few minutes"}

    # Log

    return {"error":"not implemented"}

@app.post("/features/delete/{name}", dependencies=[Depends(verified_user)])
async def delete_feature(project: Annotated[Project, Depends(get_project)],
                     name:str):
    r = project.features.delete(name)
    return r


# Models management
#------------------

@app.get("/models/simplemodel", dependencies=[Depends(verified_user)])
async def get_simplemodel(project: Annotated[Project, Depends(get_project)]):
    """
    Simplemodel parameters
    """
    r = project.simplemodels.available()
    print(type(r))
    return r


@app.post("/models/simplemodel", dependencies=[Depends(verified_user)])
async def post_simplemodel(project: Annotated[Project, Depends(get_project)],
                           simplemodel:SimpleModelModel):
    """
    Compute simplemodel
    """
    r = project.update_simplemodel(simplemodel)
    return r

@app.get("/models/bert", dependencies=[Depends(verified_user)])
async def get_bert(project: Annotated[Project, Depends(get_project)],
                   scheme:str):
    """
    bert parameters
    """
    return {"error":"Pas implémenté"}#project.bertmodel.get_params()

@app.post("/models/bert/predict", dependencies=[Depends(verified_user)])
async def predict(project: Annotated[Project, Depends(get_project)],
                     model_name:str,
                     user:str,
                     data:str = "all"):
    """
    Start prediction with a model
    """
    print("start predicting")
    df = project.content[["text"]]
    print(df[0:10])
    r = project.bertmodels.start_predicting_process(name = model_name,
                                                    df = df,
                                                    col_text = "text",
                                                    user = user)
    print("prediction launched")
    return r

@app.post("/models/bert/train", dependencies=[Depends(verified_user)])
async def post_bert(project: Annotated[Project, Depends(get_project)],
                     bert:BertModelModel):
    """ 
    Compute bertmodel
    TODO : gestion du nom du projet/scheme à la base du modèle
    """
    print("start bert training")
    df = project.schemes.get_scheme_data(bert.scheme, complete = True) #move it elswhere ?
    df = df[[project.params.col_text, "labels"]].dropna() #remove non tag data
    r = project.bertmodels.start_training_process(
                                name = bert.name,
                                user = bert.user,
                                scheme = bert.scheme,
                                df=df,
                                col_text=df.columns[0],
                                col_label=df.columns[1],
                                base_model=bert.base_model,
                                params = bert.params,
                                test_size=bert.test_size
                                )
    return r

@app.post("/models/bert/stop", dependencies=[Depends(verified_user)])
async def stop_bert(project: Annotated[Project, Depends(get_project)],
                     user:str):
    r = project.bertmodels.stop_user_training(user)
    return r

@app.post("/models/bert/rename", dependencies=[Depends(verified_user)])
async def save_bert(project: Annotated[Project, Depends(get_project)],
                     former_name:str,
                     new_name:str):
    r = project.bertmodels.rename(former_name, new_name)
    return r



# Export elements
#----------------

@app.get("/export/data", dependencies=[Depends(verified_user)])
async def export_data(project: Annotated[Project, Depends(get_project)],
                      scheme:str,
                      format:str):
    name, path = project.export_data(format=format, scheme=scheme)
    return FileResponse(path, filename=name)

@app.get("/export/features", dependencies=[Depends(verified_user)])
async def export_features(project: Annotated[Project, Depends(get_project)],
                          features:list = Query(),
                          format:str = Query()):
    name, path = project.export_features(features = features, format=format)
    return FileResponse(path, filename=name)

@app.get("/export/prediction", dependencies=[Depends(verified_user)])
async def export_prediction(project: Annotated[Project, Depends(get_project)],
                          format:str = Query(),
                          name:str = Query()):
    name, path = project.bertmodels.export_prediction(name = name, format=format)
    return FileResponse(path, filename=name)

@app.get("/export/bert", dependencies=[Depends(verified_user)])
async def export_bert(project: Annotated[Project, Depends(get_project)],
                          name:str = Query()):
    name, path = project.bertmodels.export_bert(name = name)
    return FileResponse(path, filename=name)


