import json
import os
from pydantic import BaseModel
from pydantic.tools import parse_obj_as

import functions_framework
import requests
import vertexai
from vertexai.language_models import ChatModel, InputOutputTextPair
import google.auth
import google.auth.transport.requests

URL = "https://us-central1-aiplatform.googleapis.com/v1/projects/round-ring-401308/locations/us-central1/publishers/google/models/imagetext:predict"
METHOD = "POST"

IMAGE_URI = "gs://enviroalert-processing/055d42f4-60f6-46f8-83b6-a62835885847/source/forest-fire-432870_1280.jpg"


class RequestModel(BaseModel):
    uri_source: str


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
        context="""Dado una frase determinar si se esta hablando de un incendio: Salida: {\"fire\":true/false}""",
    )
    response = chat.send_message(f"""{_data.json()['predictions'][0]}""", **parameters)
    response_data = json.loads(str(response))

    return response_data


def handle_event(request):
    # request_json = request.get_json(silent=True)
    request_json = request
    try:
        request_model = parse_obj_as(RequestModel, request_json)
        print(f"Starting with the next context:{request_model}")
    except Exception as e:
        return str(e), 400


 # Verifica que la solicitud sea una solicitud POST
    if request.method != 'POST':
        return 'La solicitud debe ser un POST', 400

    # Verifica si se proporciona un archivo 'imagen' en la solicitud
    if 'imagen' not in request.files:
        return 'No se proporcionó ninguna imagen', 400

    # Obtiene el archivo de la solicitud
    imagen = request.files['imagen']

    # Verifica que el archivo sea una imagen (puedes implementar una validación más robusta aquí)
    if not imagen.content_type.startswith('image/'):
        return 'El archivo no es una imagen válida', 400

    # Obtiene el nombre de archivo original
    nombre_archivo = imagen.filename

    # Define el nombre del bucket y la ruta donde se guardará la imagen en Cloud Storage
    bucket_name = 'enviroalert-processing'
    ruta_en_storage = 'images/' + nombre_archivo

    # Sube la imagen a Cloud Storage
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(ruta_en_storage)
    blob.upload_from_string(imagen.read(), content_type=imagen.content_type)

    # Retorna la URL de la imagen en Cloud Storage
    imagen_url = f'https://storage.googleapis.com/{bucket_name}/{ruta_en_storage}'
    return f'Imagen guardada en {imagen_url}', 200


    json_data = {
        "instances": [
            {
                "image": {
                    "gcsUri": request_model.uri_source,
                }
            },
        ],
        "parameters": {
            "sampleCount": 1,
            "storageUri": "gs://enviroalert-processing/055d42f4-60f6-46f8-83b6-a62835885847/response.txt",
            "language": "en",
        },
    }
    repsponse = request_caption(json_data)
    response = request_check_bison(response)

    return response_data


if __name__ == "__main__":
    data = {"uri_source": IMAGE_URI}
    handle_event(data)
