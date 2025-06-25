import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.docker.helper_functions import generate_context_name_from_user_workspace
from app.docker.docker_context_manager import DockerContextManager
from app.repositories.workspace_repository import WorkspaceRepository

async def main():
    email_id = "test@example.com"
    workspace = "test_workspace"
    context_name = generate_context_name_from_user_workspace(email_id, workspace)
    docker_context_manager = DockerContextManager()
    test_passed = True
    error_message = None

    # Mock the DB call to return a fake workspace with a valid vm_config.private_ip
    with patch('app.repositories.workspace_repository.WorkspaceRepository.get_workspace', new_callable=AsyncMock) as mock_get_workspace:
        class FakeVMConfig:
            private_ip = "20.244.12.2"
        class FakeWorkspace:
            vm_config = FakeVMConfig()
        mock_get_workspace.return_value = FakeWorkspace()

        try:
            # Test: create context
            print(f"Creating context: {context_name}")
            await docker_context_manager.set_context_for_user_workspace(username=email_id, workspace_name=workspace)
            context_list = os.popen("docker context ls --format '{{.Name}}'").read().splitlines()
            created = context_name in context_list
            print("Context exists after creation:", created)
            if not created:
                test_passed = False
                error_message = "Context was not created."

            # Test: remove context
            print(f"Removing context: {context_name}")
            docker_context_manager.remove_context_for_user_workspace(username=email_id, workspace_name=workspace)
            context_list = os.popen("docker context ls --format '{{.Name}}'").read().splitlines()
            removed = context_name not in context_list
            print("Context exists after removal:", not removed)
            if not removed:
                test_passed = False
                error_message = (error_message or "") + " Context was not removed."
        except Exception as e:
            test_passed = False
            error_message = str(e)

    print("\n========== FINAL REPORT ==========")
    if test_passed:
        print("TEST RESULT: SUCCESS")
    else:
        print("TEST RESULT: FAILED")
        if error_message:
            print("Reason:", error_message)
    print("==================================\n")

if __name__ == "__main__":
    asyncio.run(main())
