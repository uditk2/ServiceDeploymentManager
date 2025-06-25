import subprocess
import json
import shlex
from typing import Dict, List, Optional
import os
from app.custom_logging import logger
from app.docker.helper_functions import generate_unique_name

class DockerStats:
    """Utility class to gather statistics from Docker containers"""
    
    @staticmethod
    def get_container_stats(container_ids: List[str]) -> Dict:
        """
        Get statistics for specific Docker containers
        
        Args:
            container_ids: List of container IDs to get stats for
            
        Returns:
            Dictionary with container stats
        """
        if not container_ids:
            return {"error": "No container IDs provided"}
            
        try:
            # Format IDs for the docker stats command
            container_filter = " ".join(container_ids)
            
            # Run docker stats command with no-stream to get a single stats snapshot
            # Format as JSON for easier parsing
            cmd = f"docker stats {container_filter} --no-stream --format '{{{{json .}}}}'"
            
            process = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            success = process.returncode == 0
            
            if not success:
                logger.error(f"Error getting Docker stats: {stderr}")
                return {"error": f"Failed to get stats: {stderr}"}
                
            # Parse the JSON output
            stats = []
            for line in stdout.strip().split('\n'):
                if line:
                    try:
                        stats.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse stats JSON: {e}")
            
            # Calculate aggregated stats
            aggregated_stats = DockerStats.aggregate_container_stats(stats)
            
            return {
                "stats": stats,
                "count": len(stats),
                "aggregated": aggregated_stats
            }
                
        except Exception as e:
            logger.error(f"Error in get_container_stats: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    def aggregate_container_stats(stats: List[Dict]) -> Dict:
        """
        Aggregate statistics from multiple containers
        
        Args:
            stats: List of container statistics dictionaries
            
        Returns:
            Dictionary with aggregated statistics
        """
        if not stats:
            return {
                "cpu_percentage": 0,
                "memory_usage": "0B",
                "memory_usage_bytes": 0,
                "memory_percentage": 0,
                "network_in": "0B",
                "network_out": "0B",
                "block_in": "0B",
                "block_out": "0B"
            }
            
        try:
            total_cpu_percentage = 0
            total_memory_bytes = 0
            total_memory_percentage = 0
            total_network_in_bytes = 0
            total_network_out_bytes = 0
            total_block_in_bytes = 0
            total_block_out_bytes = 0
            
            for container in stats:
                # Handle CPU percentage (remove % sign and convert to float)
                if "CPUPerc" in container:
                    cpu_perc = container["CPUPerc"].rstrip("%")
                    try:
                        total_cpu_percentage += float(cpu_perc)
                    except ValueError:
                        logger.warning(f"Failed to parse CPU percentage: {cpu_perc}")
                
                # Handle memory usage
                if "MemUsage" in container and "/" in container["MemUsage"]:
                    memory_parts = container["MemUsage"].split(" / ")
                    if len(memory_parts) >= 1:
                        mem_usage = memory_parts[0]
                        # Convert memory string to bytes
                        mem_bytes = DockerStats._convert_size_to_bytes(mem_usage)
                        total_memory_bytes += mem_bytes
                
                # Handle memory percentage
                if "MemPerc" in container:
                    mem_perc = container["MemPerc"].rstrip("%")
                    try:
                        total_memory_percentage += float(mem_perc)
                    except ValueError:
                        logger.warning(f"Failed to parse memory percentage: {mem_perc}")
                
                # Handle network I/O
                if "NetIO" in container and "/" in container["NetIO"]:
                    net_parts = container["NetIO"].split(" / ")
                    if len(net_parts) >= 2:
                        net_in = net_parts[0]
                        net_out = net_parts[1]
                        total_network_in_bytes += DockerStats._convert_size_to_bytes(net_in)
                        total_network_out_bytes += DockerStats._convert_size_to_bytes(net_out)
                
                # Handle block I/O
                if "BlockIO" in container and "/" in container["BlockIO"]:
                    block_parts = container["BlockIO"].split(" / ")
                    if len(block_parts) >= 2:
                        block_in = block_parts[0]
                        block_out = block_parts[1]
                        total_block_in_bytes += DockerStats._convert_size_to_bytes(block_in)
                        total_block_out_bytes += DockerStats._convert_size_to_bytes(block_out)
            
            return {
                "cpu_percentage": round(total_cpu_percentage, 2),
                "memory_usage": DockerStats._convert_bytes_to_human_readable(total_memory_bytes),
                "memory_usage_bytes": total_memory_bytes,
                "memory_percentage": round(total_memory_percentage, 2),
                "network_in": DockerStats._convert_bytes_to_human_readable(total_network_in_bytes),
                "network_out": DockerStats._convert_bytes_to_human_readable(total_network_out_bytes),
                "block_in": DockerStats._convert_bytes_to_human_readable(total_block_in_bytes),
                "block_out": DockerStats._convert_bytes_to_human_readable(total_block_out_bytes)
            }
                
        except Exception as e:
            logger.error(f"Error aggregating container stats: {str(e)}")
            return {
                "error": f"Failed to aggregate stats: {str(e)}",
                "cpu_percentage": 0,
                "memory_usage": "0B",
                "memory_usage_bytes": 0,
                "memory_percentage": 0
            }
    
    @staticmethod
    def _convert_size_to_bytes(size_str: str) -> int:
        """
        Convert human readable size string to bytes
        
        Args:
            size_str: Size string (e.g. "10.5MiB", "1.2GiB")
            
        Returns:
            Size in bytes
        """
        try:
            # Remove any non-numeric prefix if present
            size_str = ''.join(c for c in size_str if c.isdigit() or c == '.' or c.isalpha())
            
            if not size_str:
                return 0
                
            units = {
                'B': 1,
                'KB': 10**3, 'KiB': 2**10,
                'MB': 10**6, 'MiB': 2**20,
                'GB': 10**9, 'GiB': 2**30,
                'TB': 10**12, 'TiB': 2**40
            }
            
            # Split number and unit
            number_part = ""
            unit_part = ""
            
            for i, char in enumerate(size_str):
                if char.isdigit() or char == '.':
                    number_part += char
                else:
                    unit_part = size_str[i:]
                    break
            
            if not number_part:
                return 0
            
            number = float(number_part)
            
            # If no unit is specified, assume bytes
            if not unit_part:
                return int(number)
            
            # Find the matching unit
            for unit, multiplier in units.items():
                if unit_part.upper().startswith(unit.upper()):
                    return int(number * multiplier)
            
            # If unit not recognized, default to bytes
            return int(number)
        except Exception as e:
            logger.warning(f"Error converting size to bytes: {str(e)}, size_str: {size_str}")
            return 0
    
    @staticmethod
    def _convert_bytes_to_human_readable(bytes_value: int) -> str:
        """
        Convert bytes to human readable string
        
        Args:
            bytes_value: Value in bytes
            
        Returns:
            Human readable string (e.g. "10.5 MiB")
        """
        try:
            if bytes_value < 0:
                return "0B"
                
            units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB']
            unit_index = 0
            
            while bytes_value >= 1024 and unit_index < len(units) - 1:
                bytes_value /= 1024.0
                unit_index += 1
            
            return f"{bytes_value:.2f}{units[unit_index]}"
        except Exception as e:
            logger.warning(f"Error converting bytes to human readable: {str(e)}")
            return "0B"
    
    @staticmethod
    def get_compose_stack_stats(compose_project_name: str) -> Dict:
        """
        Get statistics for all containers in a Docker Compose stack
        
        Args:
            compose_project_name: The name of the Docker Compose project
            
        Returns:
            Dictionary with container stats for the entire stack
        """
        try:
            # Get container IDs for the specified compose project
            cmd = f"docker compose -p {compose_project_name} ps -q"
            
            process = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            success = process.returncode == 0
            
            if not success:
                logger.error(f"Error getting Docker Compose container IDs: {stderr}")
                return {"error": f"Failed to get container IDs: {stderr}"}
            
            # Get container IDs as a list
            container_ids = [cid.strip() for cid in stdout.strip().split('\n') if cid.strip()]
            
            if not container_ids:
                return {
                    "project": compose_project_name,
                    "stats": [],
                    "count": 0,
                    "aggregated": DockerStats.aggregate_container_stats([]),
                    "message": "No running containers found for this project"
                }
            
            # Get stats for these containers
            stats_result = DockerStats.get_container_stats(container_ids)
            
            # Add project name to the result
            stats_result["project"] = compose_project_name
            
            return stats_result
            
        except Exception as e:
            logger.error(f"Error in get_compose_stack_stats: {str(e)}")
            return {"error": str(e), "project": compose_project_name}
    
    @staticmethod
    def get_workspace_stack_stats(username: str, workspace_name: str, workspace_path: str) -> Dict:
        """
        Get statistics for a workspace's Docker Compose stack
        
        Args:
            username: Username of the workspace owner
            workspace_name: Name of the workspace
            workspace_path: Path to the workspace directory
            
        Returns:
            Dictionary with stats for all containers in the workspace
        """
        try:
            # Generate unique container name based on username and workspace
            container_name = generate_unique_name(project_base_path=workspace_path, username=username)
            
            # Get statistics for this compose stack
            stats_result = DockerStats.get_compose_stack_stats(container_name)
            
            # Add additional workspace info
            stats_result["username"] = username
            stats_result["workspace_name"] = workspace_name
            
            return stats_result
            
        except Exception as e:
            logger.error(f"Error in get_workspace_stack_stats: {str(e)}")
            return {
                "error": str(e),
                "username": username, 
                "workspace_name": workspace_name,
                "stats": [],
                "aggregated": DockerStats.aggregate_container_stats([])
            }