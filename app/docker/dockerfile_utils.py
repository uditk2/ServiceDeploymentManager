import os
from .helper_functions import generate_unique_name
from app.custom_logging import logger
from .utils import DockerUtils
from .docker_log_handler import DockerCommandWithLogHandler, ContainerLogHandler
import traceback

class DockerFileUtils():

    @staticmethod
    def run_docker_stop(project_path, user_id):
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd = f'docker stop {container_name}'
            return DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            logger.error(f"Error stopping container: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def run_docker_remove(project_path, user_id):
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd =  f'docker rm {container_name}'
            return DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            logger.error(f"Error removing container: {traceback.format_exc()}")
            return None
        
    @staticmethod
    def run_docker_build(project_path, user_id):
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd = f'docker build -t {container_name} .'
            return DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            logger.error(f"Error building Docker image: {traceback.format_exc()}")
            return None

    @staticmethod    
    def _get_exposed_port_dockerfile(project_path):
        """Get the deployment port from the Dockerfile"""
        try:
            dockerfile = os.path.join(project_path, 'Dockerfile')
            if not os.path.exists(dockerfile):
                return None
            with open(dockerfile, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if 'EXPOSE' in line:
                        return line.split(' ')[1].strip()
                return None
        except Exception as e:
            logger.error(f"Error reading Dockerfile: {str(e)}")
            return None
    
    def _dev_env_deploy(project_path, container_name, port_mapping, host_port, env_file_arg):

        run_cmd = f'docker run -d --name {container_name} {port_mapping} {env_file_arg} {container_name}'
        logger.info("Run command: " + run_cmd)
        try :
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(run_cmd, container_name=container_name)
            url = f"http://localhost:{host_port}"
            if not run_result.success:
              return DockerUtils.get_build_result(container_id=None, success=False, url=None, error=f"Run failed: {run_result.error}")
            else:
              ContainerLogHandler(project_path).setup_container_logging(container_name=container_name)
              return DockerUtils.get_build_result(container_id=container_name, success=True, url=url, error=None)  
        except Exception as e:
            logger.error(f"Error in deploying in dev env {traceback.format_exc()}")
            return DockerUtils.get_build_result(container_id=None, success=False, url=None, error=f"Run failed: {str(e)}")
        
    def _prod_env_deploy(container_name, port_mapping, exposed_port, env_file_arg, project_path, user_id):
        try:
            network = DockerUtils.generate_network_labels()['network']
            traefik_labels = DockerUtils.generate_traefik_labels(container_port=exposed_port, project_path=project_path, user_id=user_id)
            label_args = " ".join([f"--label '{key}={value}'" for key, value in traefik_labels.items()])
            run_cmd = f'docker run -d --name {container_name} {port_mapping}  {env_file_arg} --network {network} {label_args} {container_name}'
            logger.info("Run command: " + run_cmd)
            url = f"https://{container_name}.synergiqai.com"
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(run_cmd, container_name=container_name) 
            if not run_result.success:
                return DockerUtils.get_build_result(container_id=None, success=False, url=None, error=f"Run failed: {run_result.error}")
            else:
                ContainerLogHandler(project_path).setup_container_logging(container_name=container_name)
                return DockerUtils.get_build_result(container_id=container_name, success=True, url=url, error=None) 
        except Exception as e:
            logger.error(f"Error in deploying in prod env {traceback.format_exc()}")
            return DockerUtils.get_build_result(container_id=None, success=False, url=None, error=f"Run failed: {str(e)}")

    @staticmethod
    def run_docker_deploy(project_path, user_id, env_file_path=None):
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        env_file_arg = ""
        if env_file_path is not None and env_file_path.strip() != "":
            env_file_arg = f"--env-file {env_file_path}"
        exposed_port = DockerFileUtils._get_exposed_port_dockerfile(project_path=project_path)
        host_port = DockerUtils.get_host_port(user_id=user_id, project_path=project_path)
        port_mapping = f"-p {host_port}:{exposed_port}" if exposed_port else f"-p {host_port}:{host_port}"
        if os.getenv('FLASK_ENV') == 'development':
            return DockerFileUtils._dev_env_deploy(project_path=project_path, container_name=container_name, 
                                                   port_mapping=port_mapping, host_port=host_port, env_file_arg=env_file_arg)
        else:
            return DockerFileUtils._prod_env_deploy(container_name=container_name, port_mapping=port_mapping, exposed_port=exposed_port,
                                                     env_file_arg=env_file_arg, project_path=project_path, user_id=user_id)
    
                

            