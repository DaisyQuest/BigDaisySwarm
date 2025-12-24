# Deploying the Example Calendar Server to Azure

The example server exposes `/healthz`, `/readyz`, `/state`, and `/dsl` (for DSL execution) using only the standard library. It is packaged as a single container that runs `python -m bigdaisyswarm.example_server`.

## Build and publish the image
```bash
RESOURCE_GROUP="calendar-example"
LOCATION="eastus"
ACR_NAME="calendarregistry$RANDOM"
IMAGE_TAG="example-server:v1"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --sku Basic
az acr login --name "$ACR_NAME"

docker build -f example_server/Dockerfile -t "$ACR_NAME.azurecr.io/calendar-example:$IMAGE_TAG" .
docker push "$ACR_NAME.azurecr.io/calendar-example:$IMAGE_TAG"
```

> **Note:** The container entrypoint boots a local PostgreSQL instance by default and exports `DATABASE_URL` pointing at it. Override `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` to connect to external databases.

## Create the App Service for Containers
```bash
az appservice plan create --name "plan-calendar-example" --resource-group "$RESOURCE_GROUP" --is-linux --sku B1
az webapp create \
  --name "calendar-example" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "plan-calendar-example" \
  --deployment-container-image-name "$ACR_NAME.azurecr.io/calendar-example:$IMAGE_TAG"

az webapp config appsettings set \
  --name "calendar-example" \
  --resource-group "$RESOURCE_GROUP" \
  --settings WEBSITES_PORT=8080

# Optional: enable a health probe for slot swaps and uptime
az webapp update \
  --name "calendar-example" \
  --resource-group "$RESOURCE_GROUP" \
  --set healthCheckPath="/readyz"
```

## Validate the deployment
- The server seeds example calendars unless `--no-seed` is provided. Hitting `/state` returns the current calendars and events as JSON.
- Run the release verification harness against the public hostname (staging slot first when available):
  ```bash
  PYTHONPATH=src python -m bigdaisyswarm.release --base-url "https://<app-name>.azurewebsites.net"
  ```
- Use `/dsl` with a JSON body to exercise the DSL remotely:
  ```bash
  curl -X POST "https://<app-name>.azurewebsites.net/dsl" \
    -H "Content-Type: application/json" \
    -d '{"commands": "CREATE_CALENDAR name=Demo owners=demo@example.com\nLIST_CALENDARS"}'
  ```

## Local smoke testing
```bash
python -m bigdaisyswarm.example_server --host 0.0.0.0 --port 8080
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
curl http://localhost:8080/state
```

## Deploy via GitHub Actions
The repo ships `.github/workflows/azure-containers.yml` to build and deploy both the example server and web client containers. Set these repository secrets before running it:
- `AZURE_CREDENTIALS`
- `ACR_NAME`, `ACR_LOGIN_SERVER`
- `AZURE_RESOURCE_GROUP`
- `WEB_CLIENT_APP_NAME`, `EXAMPLE_SERVER_APP_NAME`
The workflow tags images with the commit SHA and updates App Service container settings plus health probes (`/healthz` for the web client, `/readyz` for the example server).
