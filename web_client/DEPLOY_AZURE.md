# Deploying the Calendar Web Client to Azure

This project is a static HTML/JS client with no build step. You can deploy it to Azure Static Web Apps or an Azure Storage static website using the Azure CLI.

## Prerequisites
- Azure CLI installed and authenticated (`az login`).
- An Azure subscription with permission to create resource groups and web apps.
- The repo checked out locally. No build is required—use the contents of `web_client/`.

## Option 1: Azure Static Web Apps (recommended)
This keeps the site globally cached and requires minimal configuration.

```bash
# Variables
RESOURCE_GROUP="calendar-web"
LOCATION="eastus2"
APP_NAME="calendar-web-client-$(date +%s)"
SOURCE_DIR="$(pwd)/web_client"

# Create a resource group
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Create the static web app (no API backend)
az staticwebapp create \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --source "$SOURCE_DIR" \
  --output-location "." \
  --app-location "."
```

Notes:
- `--app-location` and `--output-location` are set to `.` because the files in `web_client/` are already final assets.
- To update later, rerun `az staticwebapp upload --name $APP_NAME --resource-group $RESOURCE_GROUP --source $SOURCE_DIR`.

## Option 2: Azure Storage static website
This uses an Azure Storage account with the static website feature enabled.

```bash
# Variables
RESOURCE_GROUP="calendar-web"
LOCATION="eastus2"
STORAGE="calendarweb$RANDOM"
SOURCE_DIR="$(pwd)/web_client"

# Create resource group and storage account
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az storage account create --name "$STORAGE" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --sku Standard_LRS

# Enable static website hosting
az storage blob service-properties update \
  --account-name "$STORAGE" \
  --static-website \
  --index-document index.html \
  --404-document index.html

# Upload the client files
az storage blob upload-batch \
  --account-name "$STORAGE" \
  --destination "\$web" \
  --source "$SOURCE_DIR"

# Fetch the public endpoint
az storage account show --name "$STORAGE" --resource-group "$RESOURCE_GROUP" --query "primaryEndpoints.web"
```

## Deployment checklist
- The entry point is `index.html`; all assets live alongside it in `web_client/`.
- No build or bundling is required; ensure files upload verbatim.
- If adding routes later, configure rewrites (e.g., `staticwebapp.config.json`) so all routes fall back to `index.html`.
- Keep `styles.css`, `app.js`, `calendar_model.mjs`, and `ui_templates.mjs` in the same directory to preserve module imports.
- To toggle remote sync, set `window.__CALENDAR_APP_CONFIG__` before loading `app.js` (see `CONFIGURATION.md`).

## Troubleshooting
- **Blank page after deploy:** verify that `app.js` is served with the correct MIME type; Azure static hosting handles this automatically when files are uploaded without renaming.
- **LocalStorage errors:** the client now falls back to in-memory storage and warns if stored state is corrupted.
- **Caching issues:** purge the CDN/endpoint or append a cache-busting query (e.g., `?v=1`) during manual validation.

## Option 3: Containerized App Service for Containers
Use the Dockerfile in `web_client/` to run the static assets behind NGINX. This is helpful when you want to publish the client alongside the example server in the same registry.

```bash
# Variables
RESOURCE_GROUP="calendar-web"
LOCATION="eastus"
ACR_NAME="calendarregistry$RANDOM"
IMAGE_TAG="web-client:v1"

# Build and push
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --sku Basic
az acr login --name "$ACR_NAME"
docker build -f web_client/Dockerfile -t "$ACR_NAME.azurecr.io/calendar-web:$IMAGE_TAG" .
docker push "$ACR_NAME.azurecr.io/calendar-web:$IMAGE_TAG"

# App Service plan + container web app
az appservice plan create --name "plan-calendar-web" --resource-group "$RESOURCE_GROUP" --is-linux --sku B1
az webapp create \
  --name "calendar-web-client" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "plan-calendar-web" \
  --deployment-container-image-name "$ACR_NAME.azurecr.io/calendar-web:$IMAGE_TAG"

# Configure the container startup
az webapp config appsettings set \
  --name "calendar-web-client" \
  --resource-group "$RESOURCE_GROUP" \
  --settings WEBSITES_PORT=80

# Point the health check at the static responder
az webapp update \
  --name "calendar-web-client" \
  --resource-group "$RESOURCE_GROUP" \
  --set healthCheckPath="/healthz"
```

Notes:
- The `web_client/nginx.conf` file sets the correct MIME type for `.mjs` modules and serves `/healthz` with HTTP 200 for Azure health probes.
- Keep `index.html`, `app.js`, `calendar_model.mjs`, and `ui_templates.mjs` together under `/usr/share/nginx/html` when customizing the image.
- If you need to inject runtime configuration, mount a short script that sets `window.__CALENDAR_APP_CONFIG__` ahead of `app.js` (see `CONFIGURATION.md`).

## Deploy via GitHub Actions (container path)
The `.github/workflows/azure-containers.yml` workflow builds this image, pushes it to ACR, and updates the configured App Service. Populate these repository secrets:
- `AZURE_CREDENTIALS` (JSON for `azure/login`)
- `ACR_NAME`, `ACR_LOGIN_SERVER` (e.g., `contoso.azurecr.io`)
- `AZURE_RESOURCE_GROUP`
- `WEB_CLIENT_APP_NAME`
- `EXAMPLE_SERVER_APP_NAME` (used by the example server deployment in the same workflow)
