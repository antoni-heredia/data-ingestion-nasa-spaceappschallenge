import json
import os
from pydantic import BaseModel, Field
from pydantic.tools import parse_obj_as

import functions_framework
import requests
import vertexai
from vertexai.language_models import ChatModel, InputOutputTextPair
import google.auth
import google.auth.transport.requests
from google.cloud import storage

URL = "https://us-central1-aiplatform.googleapis.com/v1/projects/round-ring-401308/locations/us-central1/publishers/google/models/imagetext:predict"
METHOD = "POST"


class RequestModel(BaseModel):
    author: str = Field(None, title="Author of the image")
    latitude: float = Field(..., title="Latitude of the image")
    longitude: float = Field(..., title="Longitude of the image")
    fire_type: str = Field(None, title="Type of fire")
    radius: float = Field(None, title="Radius of the fire")
    labels: str = Field(None, title="Labels of the image")


def request_caption(_data):
    creds, project = google.auth.default()

    # creds.valid is False, and creds.token is None
    # Need to refresh credentials to populate those
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    access_token = creds.token
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.post(URL, json=_data, headers=headers)
    try:
        response.raise_for_status()
    except Exception as e:
        raise e

    print(f"The caption of the image is:{response.json()['predictions'][0]}")
    return response


def request_check_bison(_data):
    vertexai.init(project="round-ring-401308", location="us-central1")
    chat_model = ChatModel.from_pretrained("chat-bison")
    parameters = {
        "max_output_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.8,
        "top_k": 40,
    }
    chat = chat_model.start_chat(
        context="""Given a sentence, determine if we are talking about a fire. Output: {\"fire\":true/false}""",
    )
    response = chat.send_message(f"""{_data.json()['predictions'][0]}""", **parameters)
    response_data = json.loads(str(response))

    return response_data


def add_row_to_bigquery(_data, image_url):
    from google.cloud import bigquery
    import datetime

    client = bigquery.Client()
    dataset_id = "fires"
    table_id = "data_user"
    dataset_ref = client.dataset(dataset_id)
    table_ref = dataset_ref.table(table_id)
    table = client.get_table(table_ref)  # API request
    timestamp = datetime.datetime.now()
    rows_to_insert = [
        (
            f"{_data['fire_type']}",
            f"{_data['latitude']}",
            f"{_data['longitude']}",
            f"{_data['labels']}",
            f"{_data['author']}",
            f"{timestamp}",
            f"{_data['radius']}",
            image_url,
        ),
    ]
    errors = client.insert_rows(table, rows_to_insert)  # API request
    if errors == []:
        print("New rows have been added.")
    else:
        print("Encountered errors while inserting rows: {}".format(errors))


def handle_event(request):
    # Check if the request has the correct format
    if "data" not in request.files:
        return "The data is not provider", 400
    data = request.files["data"].read()
    request_json = json.loads(data)
    try:
        request_model = parse_obj_as(RequestModel, request_json)
        print(f"Starting with the next context:{requeImagen subida a Cloud Storagest_model}")
    except Exception as e:
        print(e)
        return str(e), 400

    if request.method != "POST":
        return "The method of the request must be POST", 400

    if "imagen" not in request.files:
        return "Image not provide", 400

    imagen = request.files["imagen"]

    if not imagen.content_type.startswith("image/"):
        return "El archivo no es una imagen válida", 400

    nombre_archivo = imagen.filename

    bucket_name = "enviroalert-processing"
    ruta_en_storage = "images/" + nombre_archivo
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(ruta_en_storage)
    blob.upload_from_string(imagen.read(), content_type=imagen.content_type)

    print("Image uploaded with the next public url: ", blob.public_url)

    json_data = {
        "instances": [
            {
                "image": {
                    "gcsUri": f"gs://{bucket_name}/{ruta_en_storage}",
                }
            },
        ],
        "parameters": {
            "sampleCount": 1,
            "language": "en",
        },
    }
    repsponse = request_caption(json_data)
    response_data = request_check_bison(repsponse)
    if response_data["fire"]:
        add_row_to_bigquery(request_model.dict(), blob.public_url)

    return response_data
