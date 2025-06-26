##
### Docker Operations-related exceptions
##

class DockerComposeFileNotFoundException(Exception):
    """Raised when the docker-compose file is not found."""
    pass

class DockerComposeBuildFailedException(Exception):
    """Raised when docker-compose build fails."""
    pass

class DockerComposeDeployFailedException(Exception):
    """Raised when docker-compose deploy fails."""
    
    def __init__(self, message="docker-compose down failed", original_exception=None):
        message = f"{message}. Original exception: {str(original_exception)}" if original_exception else message
        super().__init__(message)
        self.original_exception = original_exception
        
class DockerComposeDownFailedException(Exception):
    """Raised when docker-compose down fails."""

    def __init__(self, message="docker-compose down failed", original_exception=None):
        message = f"{message}. Original exception: {str(original_exception)}" if original_exception else message
        super().__init__(message)
        self.original_exception = original_exception

class DockerComposeCleanupFailedException(Exception):
    """Raised when docker-compose cleanup fails."""
    pass

class DockerComposeSystemCleanupFailedException(Exception):
    """Raised when docker-compose system cleanup fails."""
    pass

class DockerContextSetException(Exception):
    """Raised when setting the Docker context fails."""
    pass
##
### VM-related exceptions
##

class VMNotFoundException(Exception):
    """Raised when a VM is not found."""
    pass
class VMAllocationCheckFailedException(Exception):
    """Raised when VM allocation check fails."""
    pass
class VMCreationFailedException(Exception):
    """Raised when VM creation fails."""
    def __init__(self, message="VM creation failed", original_exception=None):
        message = f"{message}. Original exception: {str(original_exception)}" if original_exception else message
        super().__init__(message)
        self.original_exception = original_exception
class VMInfoNotAvailableException(Exception):
    """Raised when VM information is not available."""
    pass

##
### Workspace-related exceptions
##
class WorkspaceNotFoundException(Exception):
    """Raised when a workspace is not found."""
    pass
class WorkspaceCreationFailedException(Exception):
    """Raised when workspace creation fails."""
    pass
class WorkspaceUpdateFailedException(Exception):
    """Raised when workspace update fails."""
    pass
class WorkspaceAlreadyExistsException(Exception):
    pass

class InvalidWorkspaceConfigurationException(Exception):
    """Raised when the workspace configuration is invalid."""
    pass
class WorkspaceUploadFailedException(Exception):
    """Raised when uploading a workspace fails."""
    def __init__(self, message="workspace upload failed", original_exception=None):
        message = f"{message}. Original exception: {str(original_exception)}" if original_exception else message
        super().__init__(message)
        self.original_exception = original_exception

###
## Zip-related exceptions
###
class ZipExtractionFailedException(Exception):
    """Raised when zip extraction fails."""
    def __init__(self, message="Zip extraction failed", original_exception=None):
        message = f"{message}. Original exception: {str(original_exception)}" if original_exception else message
        super().__init__(message)
        self.original_exception = original_exception