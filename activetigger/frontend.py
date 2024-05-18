import streamlit as st
import plotly.graph_objects as go
import json
import time
import requests as rq
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import importlib
import numpy as np
from io import BytesIO
import textwrap
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_option_menu import option_menu

__version__ = "0.2"
URL_SERVER = "http://0.0.0.0:5000"
update_time = 2000
st.set_page_config(page_title="pyActiveTigger v0.1")

count = st_autorefresh(interval=update_time, limit=None, key="fizzbuzzcounter")

if not "header" in st.session_state:
    st.session_state.header = None
if not "history" in st.session_state:
    st.session_state.history = []
if not "state" in st.session_state:
    st.session_state.state = None
if not 'logged_in'  in st.session_state:
    st.session_state.logged_in = False
if not 'page' in st.session_state:
    st.session_state.page = "Projects"
if not "current_project" in st.session_state:
    st.session_state.current_project = None
if not "current_element" in st.session_state:
    st.session_state.current_element = None
if not "selection" in st.session_state:
    st.session_state.selection = None
if not "sample" in st.session_state:
    st.session_state.sample = None
if not "tag" in st.session_state:
    st.session_state.tag = None

# TODO : see the computational use ...
# TODO : windows of selection -> need to move to Dash

# Interface organization
#-----------------------

def main():
    # initialize variables
    if (st.session_state.current_project) and (st.session_state.current_project != "create_new"):
        st.session_state.state = _get_state()   
    data_path = importlib.resources.files("activetigger")
    image_path = "img/active_tigger.png"
    img = open(data_path / image_path, 'rb').read()
    st.sidebar.image(img)
    st.sidebar.write(__version__)
    # start the interface
    if not st.session_state['logged_in']:
        login_page()
    else:
        app_navigation()

def login_page():
    """
    Page to log in
    """
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if _connect_user(username, password):
            st.session_state['logged_in'] = True
        else:
            st.error("Incorrect username or password")

def app_navigation():
    """
    Select page
    """
    # computation state
    if st.session_state.state:
        if st.session_state.user in st.session_state.state["bertmodels"]["training"]:
            st.session_state.bert_training = True
            st.html(f"<div style='background-color: #ffcc00; padding: 10px;'>Computing (training / predicting). Wait the process to end before launching another one.</div>")
        else:
            st.session_state.bert_training = False

    # user logged
    st.sidebar.write(f"Current user: {st.session_state.user}")

    # creating the menu
    options = ["Projects",
               "Annotate",
               "0-shot",
               "Statistics",
               "Train model",
               "Test Model",
               "Export", 
               "Documentation"]
    
    # add user management
    if st.session_state.user == "root":
        options = options + ["Configuration"]    

    with st.sidebar:
        st.session_state['page'] = option_menu("Navigate", options, menu_icon="cast")

    # navigating
    if st.session_state['page'] == "Projects":
        projects()
    elif st.session_state['page'] == "Documentation":
        documentation()
    else:
        if not st.session_state.current_project:
            st.write("Select a project first")
            return
        elif st.session_state['page'] == "Annotate":
            annotate()
        elif st.session_state['page'] == "Statistics":
            description()
        elif st.session_state['page'] == "0-shot":
            zeroshot()
        elif st.session_state['page'] == "Train model":
            bertmodels()
        elif st.session_state['page'] == "Test Model":
            test_model()
        elif st.session_state['page'] == "Export":
            export()
        elif st.session_state['page'] == "Configuration":
            configuration()   

        #if st.session_state.state:
        #    st.write(st.session_state.state)

def documentation():
    """
    Documentation page
    """
    doc = _get_documentation()
    st.write(doc)

def projects():
    """
    Projects page
    - select a project
    - create one
    """
    r = _get("/server")
    existing = r["data"]["projects"]

    # display menu
    st.title("Projects")

    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        select = st.selectbox("Select existing projects:",existing)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Load"):
            st.session_state.current_project = select
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Delete"):
            _delete_project(select)
            st.session_state.current_project = None

    if st.button("New project"):
        st.session_state.current_project = "create_new"

    # case to create a new project
    if st.session_state.current_project == "create_new":
        project_name = st.text_input("Project name", value="")
        dic_langage = {"French":"fr",
                       "English":"en",
                       "Spanish":"es"}
        language = st.selectbox("Language:",list(dic_langage))
        file = st.file_uploader("Load file (CSV or Parquet)", 
                                type=['csv', 'parquet'], 
                                accept_multiple_files=False)
        if file:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith('.parquet'):
                df = pd.read_parquet(file)
            else:
                st.error("Type not supported")
            st.dataframe(df.head())
            st.write("Select columns")
            column_id = st.selectbox("Ids:",list(df.columns))
            column_text = st.selectbox("Texts:",list(df.columns))
            column_label = st.selectbox("Labels:",list(df.columns))
            columns_context = st.multiselect("Context:",list(df.columns))
            n_train = st.number_input("N train", min_value=100, max_value=len(df),key="n_train")
            n_test = st.number_input("N test (0 if no test set)", min_value=0, max_value=len(df),key="n_test")
            cols_test = st.multiselect("Stratify by", list(df.columns))
            data = {
                    "project_name": project_name,
                    "user":st.session_state.user,
                    "col_text": column_text,
                    "col_id":column_id,
                    "col_label":column_label,
                    "cols_context": columns_context,
                    "n_train":n_train,
                    "n_test":n_test, 
                    "cols_test":cols_test,
                    "language":dic_langage[language]
                    }
            if st.button("Create"):
                _create_project(data, df, file.name)
                st.session_state.current_project = project_name

    # case a project is loaded
    if st.session_state.current_project and (st.session_state.current_project != "create_new"):
        if not st.session_state.state:
            st.session_state.state = _get_state()
        st.markdown(f"<hr>Current project loaded : {st.session_state.current_project} <br>", unsafe_allow_html=True)
        with st.expander("Manage schemes"):
            options_schemes = list(st.session_state.state["schemes"]["available"].keys())
            col1, col2 = st.columns(2)
            with col1:
                scheme = st.selectbox("Select scheme to use:", options = options_schemes, index=0, placeholder="Select a scheme")
                st.session_state.current_scheme = scheme
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Delete scheme"):
                    if scheme is not None:
                        st.write(f"Deleting scheme {scheme}")
                        _delete_scheme(scheme)
            col1, col2 = st.columns(2)
            with col1:
                new_scheme = st.text_input(label="New scheme", placeholder="New scheme name", label_visibility="hidden")
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Create scheme"):
                    if new_scheme is not None:
                        st.write(f"Creating scheme {new_scheme}")
                        _create_scheme(new_scheme)

        with st.expander("Manage features"):
            features()

    return None


def features():
    """
    Feature page
    """
    st.write("Manage features")
    c = st.session_state.state["features"]["training"]
    if not len(c) == 0:
        st.html(f"<div style='background-color: #ffcc00; padding: 10px;'>Processes currently running: {c}</div>")

    feature = st.selectbox(label="Available",
                           options = st.session_state.state["features"]["available"])
    if st.button("Delete feature"):
        if feature is not None:
            st.write(f"Deleting feature {feature}")
            _delete_feature(feature)
    
    add_feature = st.selectbox(label="Add",
                           options = list(st.session_state.state["features"]["options"].keys()))
    
    params = ""
    if add_feature in st.session_state.state["features"]["options"]:
        params = json.dumps(st.session_state.state["features"]["options"][add_feature], indent=2)
        params = st.text_area(label="Parameters", value = params, label_visibility="hidden")

    if st.button("Compute feature"):
        if add_feature is not None:
            st.write(f"Computing feature {add_feature}")
            _add_feature(add_feature, params)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.subheader("Add regex")
    regex = st.text_input(label="Regex", placeholder="Write your regex", label_visibility="hidden")
    if st.button("Create regex"):
        if regex is not None:
            st.write(f"Computing regex {regex}")
            _add_regex(regex)

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("Next step : annotate"):
        if st.session_state.current_scheme is not None:
            st.session_state.page = "Annotate"

def annotate():
    """
    Annotate page
    """
    # configure menu
    mode_selection = st.session_state.state["next"]["methods_min"]
    if _is_simplemodel():
        mode_selection = st.session_state.state["next"]["methods"]
    mode_sample = st.session_state.state["next"]["sample"]

    # default element if not defined
    if not st.session_state.selection or (st.session_state.selection=="test"):
        st.session_state.selection = mode_selection[0]
    if not st.session_state.sample:
        st.session_state.sample = mode_sample[0]
        
    # get next element with the current options
    if not "current_element" in st.session_state:
        _get_next_element()
#        st.session_state.current_element = None

    # display page
    st.title("Annotate data")
    st.write("History (reload to reset):", len(st.session_state.history))
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.session_state.selection = st.selectbox(label="Selection", 
                     options = mode_selection, 
                     #key = "selection", 
                     index = mode_selection.index(st.session_state.selection), #keep the information
                     label_visibility="hidden",
                     on_change = _get_next_element)
    with col2:
        st.session_state.sample = st.selectbox(label="Sample", 
                     options = mode_sample, 
                     #key = "sample", 
                     index = mode_sample.index(st.session_state.sample), #keep the information
                     label_visibility="hidden",
                     on_change = _get_next_element)
    with col3:
        tag_options = []
        if st.session_state.selection == "maxprob":
            tag_options = st.session_state.state["schemes"]["available"][st.session_state.current_scheme]
        st.selectbox(label="Tag", 
                    options = tag_options, 
                    key = "tag", 
                    label_visibility="hidden",
                    on_change = _get_next_element)
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Back"):
                    _get_previous_element()
    if st.session_state.current_element:
        st.markdown(f"""
            <div>{st.session_state.current_element["predict"]}</div>
            <div>{st.session_state.current_element['info']}</div>
            <div style="
                border: 2px solid #4CAF50;
                padding: 10px;
                border-radius: 5px;
                color: #4CAF50;
                font-family: sans-serif;
                text-align: justify;
                margin: 10px;
                min-height: 300px;
            ">
                {st.session_state.current_element["text"]}
            </div>

        """, unsafe_allow_html=True)

        _display_labels()

    with st.expander("Manage tags"):
        col1, col2 = st.columns(2)
        options_labels = []
        options_labels = st.session_state.state["schemes"]["available"][st.session_state.current_scheme]
        with col1:
            new_label = st.text_input(label="New label", placeholder="New label name", label_visibility="hidden")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Create label"):
                if new_label is not None:
                    st.write(f"Creating label {new_label}")
                    _create_label(new_label)
        with col1:
            label = st.selectbox(label="Label",options = options_labels, index=None, 
                                placeholder="Select a label", label_visibility="hidden")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Delete label"):
                if label is not None:
                    st.write(f"Deleting label {label}")
                    _delete_label(label)
        col1, col2 = st.columns(2)

    with st.expander("Active learning"):
        simplemodels()

    with st.expander("Projection"):
        st.selectbox(label="Method", 
                     options = list(st.session_state.state["projections"]["available"].keys()), 
                     key = "projection_method")
        st.text_area(label="Parameters", 
                     value=json.dumps(st.session_state.state["projections"]["available"]["umap"], indent=2),
                     key = "projection_params", label_visibility="hidden")
        st.multiselect(label="Features", options=st.session_state.state["features"]["available"],
                       key = "projection_features")
        if st.button("Compute"):
            st.write("Computing")
            _compute_projection()
        
        # if visualisation available, display it
        if ("projection_data" in st.session_state) and (type(st.session_state.projection_data) == str):
            r = _get_projection_data()
            if ("data" in r) and (type(r["data"]) is dict):
                st.session_state.projection_data = pd.DataFrame(r["data"],)
                if not "projection_visualization" in st.session_state:
                    st.session_state.projection_visualization = _plot_visualisation()
                    st.session_state.projection_visualization.update_layout({"uirevision": "foo"}, overwrite=True)

        if "projection_visualization" in st.session_state:
            st.plotly_chart(st.session_state.projection_visualization, use_container_width=True)            

def _display_labels():
    """
    Display labels
    """
    labels = st.session_state.state["schemes"]["available"][st.session_state.current_scheme]
    cols = st.columns(len(labels)+1)
    for col, label in zip(cols[:-1], labels):
        with col:
            if st.button(label):
                _send_tag(label)
                _get_next_element()

def description():
    """
    Description page
    """
    st.title("Statistics")
    st.subheader("Statistics")
    st.write("Description of the current data")
    statistics = _get_statistics()
    #st.markdown(statistics, unsafe_allow_html=True)
    st.dataframe(statistics, width=500)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("Display data")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.selectbox(label="Sample", options=["all","tagged","untagged","recent"], index=3, key="data_mode") 
    with col2:
        st.number_input(label="min", key="data_min", min_value=0, value=0, step=1)
    with col3:
        st.number_input(label="min", key="data_max", min_value=0, value=10, step=1)

    st.session_state.data_df = _get_table()
    

    # make the table editable
    labels =  st.session_state.state["schemes"]["available"][st.session_state.current_scheme]
    st.session_state.data_df["labels"] = (
        (st.session_state.data_df["labels"].astype("category")).cat.add_categories([l for l in labels if not l in st.session_state.data_df["labels"].unique()])
            )
    modified_table = st.data_editor(st.session_state.data_df[["labels", "text"]], disabled=["text"])

    if st.button(label="Send changes"):
        st.write("Send changes")
        print(modified_table)
        _send_table(modified_table)

def zeroshot():
    """
    Zero-shot annotation panel
    """
    st.title("Use zero-shot annotation")
    st.subheader("API connexion")

    if not "api_token" in st.session_state:
        st.session_state.api_token = "Enter a valid token"

    col1, col2 = st.columns(2)
    with col1:
        api = st.selectbox("API", options=["OpenAI"], key="api")
    with col2:
        st.session_state.api_token = st.text_input("Token", value = st.session_state.api_token)

    st.subheader("Codebook")
    st.write("Describe for each label the rules to code them")

    labels = st.session_state.state["schemes"]["available"][st.session_state.current_scheme]
    codebook = st.text_area("Codebook", value=json.dumps({i:"Write the rule" for i in labels}, indent=2), key = "codebook")
    prompt = None

    if st.button("Predict annotation for 5 texts"):
        prompt = "Annotate the following list of texts with the label the most appropriate based on the given descriptions. Keep the order. Do not provide explanations. Return the result in JSON format.\n\n"
        prompt += "Labels with their descriptions:\n"
        for label, description in json.loads(codebook).items():
            prompt += f"- {label}: {description}\n"
        r = _start_zeroshot(api, st.session_state.api_token, prompt)
        if r["status"]=="error":
            st.write(r["message"])
    
    st.subheader("Results")

    if pd.notna(st.session_state.state["zeroshot"]["data"]):
        if st.session_state.state["zeroshot"]["data"] == "computing":
            st.write("Computation launched")
        else:
            df = pd.read_json(st.session_state.state["zeroshot"]["data"], 
                                    dtype={"index":str}).set_index("index")
            df["zero_shot"] = (df["zero_shot"].astype("category")).cat.add_categories([l for l in labels if not l in df["zero_shot"].unique()])
            st.session_state.df_zeroshot = st.data_editor(df[["zero_shot", "text"]], disabled=["text"])
            if st.button("Save annotations"):
                _send_table(st.session_state.df_zeroshot, labels="zero_shot")
                st.write("Save annotations")
    else:
        st.write("No prediction available; wait results if you launched it.")

def _start_zeroshot(api, token, prompt):
    """
    Launch 0-shot annotation for 10 elements
    """
    data = {
            "prompt":prompt,
            "api":api, 
            "token":token,
            "scheme":st.session_state.current_scheme
            }
    r = _post(route="/elements/zeroshot", 
            params = {"project_name":st.session_state.current_project},
            json_data=data
            )
    if r["status"] == "error":
        print(r["message"])
        st.write(r["message"])
        return False
    return r

def simplemodels():
    """
    Simplemodel page
    """
    if not "computing_simplemodel" in st.session_state:
        st.session_state.computing_simplemodel = False

    current_model = None
    statistics = ""
    params = None
    status = ""

    # if a model has already be trained for the user and the scheme
    if (st.session_state.user in st.session_state.state["simplemodel"]["available"]) \
        and (st.session_state.current_scheme in st.session_state.state["simplemodel"]["available"][st.session_state.user]):
        status = "Trained"
        current_model = st.session_state.state["simplemodel"]["available"][st.session_state.user][st.session_state.current_scheme]
        statistics = f"F1: {round(current_model['statistics']['weighted_f1'],2)} - accuracy: {round(current_model['statistics']['accuracy'],2)}"
        params = json.dumps(current_model["params"], indent=2)
        current_model = current_model['name']

    # if there is a model under training
    if (st.session_state.user in st.session_state.state["simplemodel"]["training"]) \
        and (st.session_state.current_scheme in st.session_state.state["simplemodel"]["training"][st.session_state.user]):
        status = "Computing"
        st.session_state.computing_simplemodel = True

    st.title("Active learning")
    st.write("Configure active learning model") 
    st.markdown(f"<b>{status}</b> - Current model: {current_model} <br> {statistics}",
                unsafe_allow_html=True)

    available_models = list(st.session_state.state["simplemodel"]["options"].keys())
    index = 0
    if current_model:
        index = available_models.index(current_model)
    st.selectbox(label="Model", key = "sm_model", 
                 options = available_models, 
                 index = index)
    # display current params if same model else default params
    params = json.dumps(st.session_state.state["simplemodel"]["options"][st.session_state.sm_model],indent=2)
    sm = _get_simplemodel()
    if sm and sm["name"]==st.session_state.sm_model:
        params = json.dumps(sm["params"]) # current params
    st.text_area(label="Parameters", key = "sm_params", 
                 value=params, label_visibility="hidden")
    st.multiselect(label = "Features", key = "sm_features", 
                   options=list(st.session_state.state["features"]["available"]))
    st.slider(label="Training frequency", min_value=5, max_value=100, step=1, key="sm_freq")
    if st.button("Train"):
        st.write("Train model")
        _train_simplemodel()

def bertmodels():
    """
    Bertmodel page
    TODO : améliorer la présentation
    """
    st.title("Train model")
    st.write("Train, test and predict with final model") 

    st.subheader("Existing models")

    available_bert = []
    if st.session_state.current_scheme in st.session_state.state["bertmodels"]["available"]:
        available_bert = list(st.session_state.state["bertmodels"]["available"][st.session_state.current_scheme].keys())
    st.selectbox(label="BertModels", options = available_bert, key = "bm_trained", label_visibility="hidden")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Compute prediction"):
            st.write("Compute prediction")
            _bert_prediction()
            # add variable "aleready computed"
    with col2:
        if st.button("Delete"):
            st.write("Delete model")
            _delete_bert()
    
    with col3:
        with st.expander("Rename"):
            st.text_input(label = "", value="", placeholder="New name", key="bm_new_name")
            if st.button("Validate"):
                st.write("Rename", st.session_state.bm_new_name)
                _save_bert()

    with st.expander("Description"):
        st.write("Elements")
        data = _bert_informations()
        if data:
            st.pyplot(data[0])
            st.html(data[1])

    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("Training model")
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox(label="Select model", 
                    options = st.session_state.state["bertmodels"]["options"], 
                    key = "bm_train")
    with col2:
        # TO IMPLEMENT BACKEND
        st.text_input("HuggingFace model to use", key="bm_train_hf", disabled=True, placeholder="Not implemented yet")
    st.text_area(label="Parameters", key = "bm_params", 
                 value=json.dumps(st.session_state.state["bertmodels"]["base_parameters"], 
                                  indent=2))
    
    if not st.session_state.bert_training:
        if st.button("⚙️Train"):
            st.write("⚙️Train")
            _start_bertmodel()
    else:
        if st.button("⚙️Stop"):
            st.write("⚙️Stop")
            _stop_bertmodel()

def export():
    """
    Export page
    """
    st.title("Export")

    st.write("Export your data and models") 

    col1, col2 = st.columns((2,10))
    with col1:
        st.selectbox(label="Format", options=["csv", "parquet"], key="export_format")

    with st.expander("Annotated data"):
        st.download_button(label="Download", 
                        data=_export_data(), 
                        file_name=f"annotations.{st.session_state.export_format}")

    with st.expander("Features"):
        col1, col2 = st.columns((5,5))
        with col1:
            st.multiselect(label="Export features", options=st.session_state.state["features"]["available"],
                            key="export_features", label_visibility="hidden")

        if st.session_state.export_features:
            st.download_button(label="Download", 
                                data=_export_features(), 
                                file_name=f"features.{st.session_state.export_format}")


    with st.expander("Bert"):
        # list available models
        available = []
        if st.session_state.current_scheme in st.session_state.state["bertmodels"]["available"]:
            available = st.session_state.state["bertmodels"]["available"][st.session_state.current_scheme]
        
        col1, col2 = st.columns((5,10))
        with col1:
            st.selectbox(label="Bert Model", options=available, key="bert_model", 
                        index=None, placeholder="Choose a model", label_visibility="hidden")

        if st.session_state.bert_model:
            st.download_button(label="Download model", 
                            data=_export_model(), 
                            file_name=f"{st.session_state.bert_model}.tar.gz")
            
            # TODO : test if available ...
            st.download_button(label="Download predictions", 
                            data=_export_predictions(), 
                            file_name=f"predictions.{st.session_state.export_format}")

def configuration():
    """
    Configuration panel
    - User creation
    """
    st.title("Configuration")
    st.subheader("User management")

    col1, col2 = st.columns(2)
    with col1:
        existing_users = _get_users()
        users = st.selectbox("Existing users:",existing_users)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Delete"):
            _delete_user()
            st.write("Delete user")

    st.write("Add user")
    col1, col2, col3 = st.columns(3)
    with col1:
        new_user = st.text_input("New user")
    with col2:
        new_password = st.text_input("Password")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create"):
            _create_user(new_user, new_password)
            st.write("Create user")

def test_model():
    """
    Test annotation interface
    """
    st.title("Test the model")
    st.write("Annotate an independant dataset for testing the model")
    #"TODO : display the number of elements ? How many to code ?"
    # TODO : display only if bertmodel trained ?

    available_bert = []
    if st.session_state.current_scheme in st.session_state.state["bertmodels"]["available"]:
        available_bert = list(st.session_state.state["bertmodels"]["available"][st.session_state.current_scheme].keys())
    
    # selection
    model_to_test = st.selectbox(label="Trained models", 
                 options = available_bert, 
                 key = "bm_trained_test")

    # case there is no test set
    if not st.session_state.state["params"]["test"]:
        file = st.file_uploader("Load file (CSV or Parquet)", 
                        type=['csv', 'parquet'], 
                        accept_multiple_files=False)
        if file:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith('.parquet'):
                df = pd.read_parquet(file)
            else:
                st.error("Type not supported")
        # TODO : send the file to load 
    else:
        # setting parameters to get test elements
        with st.expander("Annotating the test sample"):
            if st.session_state.selection != "test":
                st.session_state.selection = "test"
                st.session_state.tag = None
                st.session_state.sample = "untagged"
                st.session_state.frame = None
                _get_next_element()
            st.markdown(f"""
                <div style="
                    border: 2px solid #4CAF50;
                    padding: 10px;
                    border-radius: 5px;
                    color: #4CAF50;
                    font-family: sans-serif;
                    text-align: justify;
                    margin: 10px;
                    min-height: 300px;
                ">
                    {st.session_state.current_element["text"]}
                </div>
            """, unsafe_allow_html=True)
            _display_labels()

        # panel for computation and results
        with st.expander("Compute metrics"):
            # launch computation if needed
            if st.button("Launch prediction & stats"):
                _compute_test(model_to_test, st.session_state.current_scheme)

            # display existing statistics
            informations = _bert_test_informations(model_to_test)
            if informations:
                st.write(informations)


# Internal functions
# ------------------

def _post(route:str, 
        params:dict|None = None, 
        files:str|None = None,
        json_data:dict|None = None,
        data:dict|None = None) -> dict:
    """
    Post to API
    """
    url = URL_SERVER + route
    r = rq.post(url, 
                params = params,
                json = json_data,
                data = data,
                files = files,
                headers = st.session_state.header, 
                verify = False)
    #print(url, r.content, st.session_state.header)
    if r.status_code == 422:
        return {"status":"error", "message":"Not authorized"}
    return json.loads(r.content)

def _get(route:str, 
        params:dict|None = None, 
        data:dict|None = None,
        is_json = True) -> dict:
    """
    Get from API
    """
    url = URL_SERVER + route
    r = rq.get(url, 
                params = params,
                data = data,
                headers = st.session_state.header,
                verify=False)
    #print(url, r.content, st.session_state.header)
    if r.status_code == 422:
        return {"status":"error", "message":"Not authorized"}
    if is_json:
        return json.loads(r.content)
    return r.content

def _get_documentation():
    """
    Get documentation
    """
    r = _get(route = f"/documentation")
    if r["status"] == "error":
        print(r["message"])
        st.write(r["message"])
        return r["message"]
    return r["data"]

def _connect_user(user:str, password:str) -> bool:
    """
    Connect account and get auth token
    """
    form = {
            "username":user,
            "password":password
            }
    
    r = _post("/token", data = form)
    if not "access_token" in r:
        print(r)
        return False

    # Update widget configuration
    st.session_state.header = {"Authorization": f"Bearer {r['access_token']}", "username":user}
    st.session_state.user = user
    return True

def _get_state() -> dict:
    """
    Get state variable
    """
    # only if a current project is selected
    if "current_project" in st.session_state:
        state = _get(route = f"/state/{st.session_state.current_project}")
        if state["status"]=="error":
            print(state)
            return {}
        return state["data"]
    return {}


def _get_users():
    """
    Get existing users
    """
    r = _get(route="/users")
    return r["data"]["users"]

def _create_user(username:str, password:str):
    """
    Create user
    """
    params = {"username":username,
              "password":password, 
              "projects":"all"}
    r = _post(route="/users/create", 
                params=params
                )
    if r["status"] == "error":
        print(r["message"])
        st.write(r["message"])
        return False
    return r

def _delete_user(username:str):
    """
    Delete user
    """
    params = {"username":username}
    r = _post(route="/users/delete", 
                params=params
                )
    if r["status"] == "error":
        print(r["message"])
        st.write(r["message"])
        return False
    return r    

def _create_project(data, df, name):
    """
    Create project
    """
    buffer = BytesIO()
    df.to_csv(buffer)
    buffer.seek(0)
    files = {'file': (name, buffer)}
    r = _post(route="/projects/new", 
                files=files,
                data=data
                )
    print("Retour", r)
    if r["status"] == "error":
        print(r["message"])
    return True

def _delete_project(project_name:str) -> dict:
    """
    Delete existing project
    """
    params = {
            "project_name": project_name,
            "user":st.session_state.user
            }  
    r = _post(route = "/projects/delete", 
              params = params)
    return r

def _create_scheme(s:str):
    """
    Create new scheme
    """
    if s == "":
        return "Empty"
    params = {
            "project_name":st.session_state.current_project
            }
    data = {
        "project_name": st.session_state.current_project,
        "name":s,
        "tags":[],
            }
    r = _post("/schemes/add", 
                params = params, 
                json_data = data)
    return r

def _create_label(label:str):
    """
    Create label in a scheme
    """
    if label == "":
        return "Empty"
    params = {"project_name":st.session_state.current_project,
                "scheme": st.session_state.current_scheme,
                "label":label,
                "user":st.session_state.user}
    r = _post("/schemes/label/add", 
                    params = params)
    return r

def _delete_scheme(s:str):
    """
    Delete scheme
    """
    if s == "":
        return "Empty"
    params = {"project_name":st.session_state.current_project}
    data = {
            "project_name":st.session_state.current_project,
            "name":s,
            }
    r = _post("/schemes/delete", 
                params = params, 
                json_data = data)
    return r

def _delete_label(label:str):
    """
    Delete label in a scheme
    """
    if label == "":
        return "Empty"
    params = {"project_name":st.session_state.current_project,
                "scheme":st.session_state.current_scheme,
                "label":label,
                "user":st.session_state.user}
    r = _post("/schemes/label/delete", 
                    params = params)
    return r

def _delete_feature(feature_name) -> bool:
    """
    Delete existing feature
    """
    r = _post(f"/features/delete/{feature_name}", 
                params = {"project_name":st.session_state.current_project,
                            "user":st.session_state.user})
    return True

def _add_feature(feature_name, feature_params) -> bool:
    """
    Compute feature
    """
    if not feature_name in st.session_state.state["features"]["options"].keys():
        return "This feature doesn't exist"
    try:
        feature_params = json.loads(feature_params)
    except:
        raise ValueError("Problem in the json parameters")
    r = _post(f"/features/add/{feature_name}", 
                params ={
                        "project_name":st.session_state.current_project,
                        "user":st.session_state.user
                        },
                json_data = {"params":feature_params}
                )
    return True

def _add_regex(value:str, name:str|None = None) -> bool:
    """
    Add regex as feature
    """
    if name is None:
        name = value
    
    name = f"regex_{st.session_state.user}_{name}"

    data = {
        "project_name":st.session_state.current_project,
        "name":name,
        "value":value,
        "user":st.session_state.user
        }
    
    r = _post("/features/add/regex",
        params = {"project_name":st.session_state.current_project},
        json_data=data)
    return True

def _get_next_element() -> bool:
    """
    Get next element from the current widget options
    """
    # try:
    #     f = visualization.children[0]
    #     x1y1x2y2 = [f['layout']['xaxis']['range'][0], 
    #                 f['layout']['yaxis']['range'][0],
    #                 f['layout']['xaxis']['range'][1], 
    #                 f['layout']['yaxis']['range'][1]]
    # except:
    #     x1y1x2y2 = []
    x1y1x2y2 = []

    # params = {
    #         "project_name":st.session_state.current_project,
    #         "user":st.session_state.user,
    #         "scheme":st.session_state.current_scheme,
    #         "selection":st.session_state.selection,
    #         "sample":st.session_state.sample,
    #         "tag":st.session_state.tag,
    #         "history":st.session_state.history,
    #         "frame":x1y1x2y2
    #         }
    params = {
            "project_name":st.session_state.current_project,
            "user":st.session_state.user
    }
    data = {
            "scheme":st.session_state.current_scheme,
            "selection":st.session_state.selection,
            "sample":st.session_state.sample,
            "tag":st.session_state.tag,
            "history":st.session_state.history,
            "frame":x1y1x2y2
            }
    
    print(data)
    # r = _get(route = "/elements/next",
    #                 params = params)
    r = _post(route = "/elements/next",
              params = params,
              json_data = data)

    print(r)
    if r["status"] == "error":
        print(r["message"])
        st.write(r["message"])
        return False

    st.session_state.current_element = r["data"]
#    self._textarea.value = self.current_element["text"]
#    self.info_element.value = str(self.current_element["info"])
#    self.info_predict.value = f"Predict SimpleModel: <b>{self.current_element['predict']['label']}</b> (p = {self.current_element['predict']['proba']})"
    return True

def _send_tag(label):
    data = {
            "project_name":st.session_state.current_project,
            "scheme":st.session_state.current_scheme,
            "element_id":st.session_state.current_element["element_id"],
            "tag":label,
            "user":st.session_state.user,
            "selection":st.session_state.current_element["selection"] #mode of selection of the element
            }
    
    r = _post(route = "/tags/add",
                    params = {"project_name":st.session_state.current_project},
                    json_data = data)
    
    # add in history
    if "error" in r:
        st.write(r)
    else:
        st.session_state.history.append(st.session_state.current_element["element_id"])

    # TODO # check if simplemodel need to be retrained
    # if self.is_simplemodel() and (len(self.history) % self.simplemodel_autotrain.value == 0):
    #     sm = self.state["simplemodel"]["available"][self.user][self.select_scheme.value]
    #     self.create_simplemodel(self.select_scheme.value,
    #                 model = sm["name"], 
    #                 parameters = sm["params"], 
    #                 features = sm["features"])


def _display_element(element_id):
    """
    Display specific element
    """
    r = _get(route = f"/elements/{element_id}",
                    params = {"project_name":st.session_state.current_project,
                            "scheme":st.session_state.current_scheme})
    # Managing errors
    if r["status"]=="error":
        print(r)
        return False
    # Update interface
    print(r["data"])
    st.session_state.current_element = r["data"]
    return True

def _get_previous_element() -> bool:
    """
    Load previous element in history
    """
    if len(st.session_state.history) == 0:
        st.write("No element in history")
        return False
    element_id = st.session_state.history.pop()
    r = _display_element(element_id) 
    return r

def _compute_projection():
    """
    Start computing projection
    """
    params = {
            "project_name":st.session_state.current_project,
            "user":st.session_state.user
            }
    
    try:
        proj_params = json.loads(st.session_state.projection_params)
    except:
        raise ValueError("Problem in the json parameters")

    data = {
        "method":st.session_state.projection_method, 
        "features":st.session_state.projection_features,
        "params":proj_params,
        }
    
    r = _post("/elements/projection/compute",
        params = params,
        json_data = data)
    if r["status"] == "waiting":
        st.session_state.projection_data = "computing"
        st.write(st.session_state.projection_data)
    else:
        print(r)

def _plot_visualisation():
    """
    Produce the visualisation for the projection
    """
    df = st.session_state.projection_data
    df["to_show"] = df.apply(lambda x : f"{x.name}<br>{'<br>'.join(textwrap.wrap(x['texts'][0:300],width=30))}...", axis=1)
    f = go.FigureWidget([go.Scatter(x=df[df["labels"]==i]["0"], 
                                    y=df[df["labels"]==i]["1"], 
                                    mode='markers', 
                                    name = i,
                                    customdata = np.stack((df[df["labels"]==i]["to_show"],), axis=-1),
                                    hovertemplate="%{customdata[0]}",
                                    showlegend = True) for i in df["labels"].unique()])
    f.layout.hovermode = 'closest'
    def update_point(trace, points, selector):
        # select specific text
        if len(points.point_inds)>0:
            element_id = trace.customdata[points.point_inds][0][0].split("<br>")[0] #TODO améliorer
            _display_element(element_id)
    for i in range(0,len(f.data)):
        f.data[i].on_click(update_point)
    return f

def _get_projection_data():
    """
    Get projection data
    """
    params = {
            "project_name":st.session_state.current_project, 
            "user":st.session_state.user,
            "scheme":st.session_state.current_scheme
            }
    r = _get("/elements/projection/current",
        params = params)
    return r

def _get_statistics():
    params = {"project_name":st.session_state.current_project, 
            "scheme":st.session_state.current_scheme, 
            "user":st.session_state.user}
    r = _get("/description",params = params)
    if r["status"]=="error":
        return r["message"]
    #text = ""
    tab = pd.DataFrame([[k,v] for k,v in r["data"].items()], columns=["information","values"]).set_index("information")
    #for k,v in r["data"].items():
    #    text += f"<br>- <b>{k}</b>: {v}"
    #return text
    return tab

def _get_table():
    """
    Get data as a table
    """
    params = {
                "project_name":st.session_state.current_project,
                "scheme":st.session_state.current_scheme,
                "min":st.session_state.data_min,
                "max":st.session_state.data_max,
                "mode":st.session_state.data_mode
                }
    r = _get("/elements/table", params = params)
    df = pd.DataFrame(r["data"])
    return df

def _send_table(df, labels="labels"):
    """
    Send table modified
    """

    def replace_na(i):
        if pd.isna(i):
            return None
        return i
    data = {
        "scheme":st.session_state.current_scheme,
        "list_ids": list(df.index), #list(st.session_state.data_df.index),
        "list_labels": [replace_na(i) for i in df[labels]], #[replace_na(i) for i in st.session_state.data_df["labels"]]
    }
    r = _post("/elements/table", 
                json_data = data, 
                params = {"project_name":st.session_state.current_project,
                            "user":st.session_state.user
                            })
    if r["status"] == "error":
        st.write(r["message"])
    st.write("Data saved")

def _train_simplemodel():
    """
    Create a simplemodel
    """
    if (st.session_state.sm_features is None) or (len(st.session_state.sm_features)==0):
        return "Need at least one feature" 
    params = {"project_name":st.session_state.current_project}
    if type(st.session_state.sm_params) is str:
        try:
            parameters = json.loads(st.session_state.sm_params)
        except:
            print(st.session_state.sm_params)
            raise ValueError("Problem in the json parameters")
    data = {
            "model":st.session_state.sm_model,
            "features":st.session_state.sm_features,
            "params":parameters,
            "scheme":st.session_state.current_scheme,
            "user":st.session_state.user
            }
    r = _post("/models/simplemodel", 
                    params = params, 
                    json_data = data)
    if r["status"] == "error":
        st.write(r["message"])
        return False
    st.write("Computing model")
    return True

def _bert_prediction():
    """
    Start prediction
    """
    if st.session_state.bm_trained is None:
        return False
    params = {"project_name":st.session_state.current_project,
            "user":st.session_state.user,
            "model_name":st.session_state.bm_trained
            }
    r = _post("/models/bert/predict", 
            params = params)
    if r["status"]=="error":
        print(r["message"])
    return True

def _bert_test_informations(model):
    params = {
                "project_name":st.session_state.current_project,
                "name":model
                }
    r = _get("/models/bert", params = params)
    if r["status"] == "error":
        print(r)
        return None
    if not 'test_scores' in r["data"]:
        return None
    return r["data"]['test_scores']

def _bert_informations():
    """
    Return statistics for a BERT Model
    """
    if st.session_state.bm_trained is None:
        return False
    params = {
            "project_name":st.session_state.current_project,
            "name":st.session_state.bm_trained
            }
    r = _get("/models/bert", params = params)
    if r["status"] == "error":
        print(r)
        return False

    loss = pd.DataFrame(r['data']["training"]["loss"])
    fig, ax = plt.subplots(figsize=(3,2))
    loss.plot(ax = ax)
    text = ""
    if "f1" in r['data']["train_scores"]:
        text+=f"f1: {r['data']['train_scores']['f1']}<br>"
        text+=f"precision: {r['data']['train_scores']['precision']}<br>"
        text+=f"recall: {r['data']['train_scores']['recall']}<br>"
    else:
        text += "Compute prediction for scores"
    return fig, text

def _delete_bert():
    """
    Delete bert model
    """
    params = {"project_name":st.session_state.current_project,
              "bert_name":st.session_state.bm_trained,
              "user":st.session_state.user
            }
    r = _post("/models/bert/delete", 
                    params = params)
    return r

def _save_bert():
    """
    Rename model
    """
    params = {"project_name":st.session_state.current_project,
                "former_name":st.session_state.bm_trained,
                "new_name":st.session_state.bm_new_name,
                "user":st.session_state.user
                }
    r = _post("/models/bert/rename",
        params = params)
    return r

def _start_bertmodel():
    """
    Start bertmodel training
    """
    try:
        bert_params = json.loads(st.session_state.bm_params)
    except:
        raise ValueError("Problem in the json parameters")
    
    params = {"project_name":st.session_state.current_project}

    # Specific or generic model
    model_name = st.session_state.bm_train
    if st.session_state.bm_train_hf:
        model_name = st.session_state.bm_train_hf

    data = {
            "project_name":st.session_state.current_project,
            "scheme":st.session_state.current_scheme,
            "user":st.session_state.user,
            "name":f"_{st.session_state.user}", # générique
            "base_model":model_name,
            "params":bert_params,
            "test_size":0.2
            }
    
    r = _post("/models/bert/train", 
                    params = params, 
                    json_data = data)
    time.sleep(2)
    st.session_state.bert_training = True
    return True

def _stop_bertmodel():
    """
    Stop bertmodel training
    """
    params = {"project_name":st.session_state.current_project,
                "user":st.session_state.user}
    r = _post("/models/bert/stop", 
            params = params)
    time.sleep(2)
    st.session_state.bert_training = False
    return True

@st.cache_data
def _export_data():
    """
    Get exported data
    """
    params = {"project_name":st.session_state.current_project,
                "scheme":st.session_state.current_scheme, #current scheme
                "format":st.session_state.export_format
                }
    r = _get("/export/data",
        params = params,
        is_json= False)
    return r

@st.cache_data
def _export_features():
    """
    Get exported features
    """
    if len(st.session_state.export_features)==0:
        st.write("Error")
        return None
    
    params = {"project_name":st.session_state.current_project,
                "features":st.session_state.export_features,
                "format":st.session_state.export_format
                }
    r = _get("/export/features",
        params = params,
        is_json= False)
    return r

@st.cache_data
def _export_predictions():
    """
    Get exported prediction for a BERT model
    """
    params = {"project_name":st.session_state.current_project,
                "name":st.session_state.bert_model,
                "format":st.session_state.export_format
                }
    r = _get("/export/prediction",
        params = params,
        is_json= False)
    return r

@st.cache_data
def _export_model():
    """
    Get BERT Model
    """
    params = {"project_name":st.session_state.current_project,
               "name":st.session_state.bert_model,
                }
    r = _get("/export/bert",
        params = params,
        is_json= False)
    if type(r) is dict:
        print(r)
        return None
    return r

def _is_simplemodel():
    """
    simplemodel trained for scheme/user
    """
    if st.session_state.user in st.session_state.state["simplemodel"]["available"]:
        if st.session_state.current_scheme in st.session_state.state["simplemodel"]["available"][st.session_state.user]:
            return True
    return False

def _get_simplemodel():
    if _is_simplemodel():
        return st.session_state.state["simplemodel"]["available"][st.session_state.user][st.session_state.current_scheme]
    return None

def _compute_test(model_name, scheme):
    params = {"project_name":st.session_state.current_project,
              "scheme":scheme,
              "model":model_name
              }
    r = _post("/models/bert/test", 
            params = params)
    if r["status"]=="error":
        print(r["message"])
        return False
    return True    

if __name__ == "__main__":
    main()