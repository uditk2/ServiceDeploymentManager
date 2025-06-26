from service_deployment_manager_client import ServiceDeploymentManagerClient



client = ServiceDeploymentManagerClient(base_url="http://localhost:8005")

def test_workspace_repository(username, workspace):
    """Test the workspace repository API."""
    print(f"Testing workspace repository for user: {username}, workspace: {workspace}")

    # Step 1: Get workspace
    result = client.get_workspace(username, workspace)
    result.json()  # Ensure we can access the workspace
    if result.status_code != 200:
        print(f"Failed to get workspace: {result.status_code} - {result.text}")
        return False
    workspace_data = result.json()
    print(f"Workspace {workspace_data} retrieved successfully.")
    return True
def test_workspace_delete_repository():
    """Test the workspace delete repository API."""
    print("Testing workspace delete repository...")

    # Step 1: Delete workspace
    username = "uditk2@gmail.com"
    workspace = "AdventureousChemist"
    result = client.delete_workspace(username, workspace)
    if result.status_code != 200:
        print(f"Failed to delete workspace: {result.status_code} - {result.text}")
        return False
    print(f"Workspace {workspace} deleted successfully.")
    return True

if __name__ == "__main__":

    username = "uditk2@gmail.com"
    workspace = "AdventureousChemist"
    if test_workspace_repository(username=username, workspace=workspace):
        print("Workspace repository test passed!")
    else:
        print("Workspace repository test failed!")
