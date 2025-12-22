from pathlib import Path


WORKFLOW = Path('.github/workflows/azure-containers.yml')


def test_azure_containers_workflow_exists_and_uses_secrets():
    content = WORKFLOW.read_text(encoding='utf-8')
    assert 'azure/login@' in content
    assert 'docker/build-push-action@' in content
    assert 'web_client/Dockerfile' in content
    assert 'example_server/Dockerfile' in content
    for secret in [
        'AZURE_CREDENTIALS',
        'ACR_NAME',
        'ACR_LOGIN_SERVER',
        'AZURE_RESOURCE_GROUP',
        'WEB_CLIENT_APP_NAME',
        'EXAMPLE_SERVER_APP_NAME',
    ]:
        assert f"secrets.{secret}" in content
    assert 'healthCheckPath="/healthz"' not in content
    assert 'healthCheckPath="/readyz"' not in content


def test_workflow_tags_use_sha():
    content = WORKFLOW.read_text(encoding='utf-8')
    assert '${{ env.IMAGE_TAG }}' in content
    assert 'IMAGE_TAG: ${{ github.sha }}' in content
