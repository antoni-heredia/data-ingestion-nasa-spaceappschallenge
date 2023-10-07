# data-ingestion-nasa-spaceappschallenge

curl -X POST -H "Content-Type: multipart/form-data" \
  -F "imagen=@imagen.jpeg" \
  -F "data=@datos.json" \
   https://europe-west1-round-ring-401308.cloudfunctions.net/image_processing