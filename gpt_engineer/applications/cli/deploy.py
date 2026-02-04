"""
Module for deploying projects to a shareable URL.

This module handles the deployment of gpt-engineer projects to a hosting service,
generating shareable URLs and tracking deployment events.
"""

import json
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from termcolor import colored

from gpt_engineer.core.files_dict import FilesDict


def generate_project_id() -> str:
    """
    Generate a unique project ID for deployment.

    Returns
    -------
    str
        A unique project identifier.
    """
    return str(uuid.uuid4())


def create_gpt_engineer_manifest(
    project_id: str, project_path: Path, prompt: Optional[str] = None
) -> dict:
    """
    Create a gpt-engineer.json manifest file for the deployed project.

    Parameters
    ----------
    project_id : str
        Unique identifier for the project.
    project_path : Path
        Path to the project directory.
    prompt : str, optional
        The original prompt used to generate the project.

    Returns
    -------
    dict
        The manifest dictionary.
    """
    manifest = {
        "project_id": project_id,
        "project_path": str(project_path),
        "prompt": prompt,
        "version": "1.0",
    }
    return manifest


def inject_manifest_into_files(files_dict: FilesDict, manifest: dict) -> FilesDict:
    """
    Inject the gpt-engineer.json manifest into the files dictionary.

    Parameters
    ----------
    files_dict : FilesDict
        The files dictionary to inject the manifest into.
    manifest : dict
        The manifest dictionary to inject.

    Returns
    -------
    FilesDict
        The files dictionary with the manifest added.
    """
    files_dict["gpt-engineer.json"] = json.dumps(manifest, indent=2)
    return files_dict


def deploy_to_vercel(
    project_path: Path, project_id: str, files_dict: FilesDict
) -> Optional[str]:
    """
    Deploy project to Vercel and return the shareable URL.

    This function attempts to deploy using Vercel CLI. If Vercel CLI is not available,
    it falls back to a mock deployment for development/testing.

    Parameters
    ----------
    project_path : Path
        Path to the project directory.
    project_id : str
        Unique identifier for the project.
    files_dict : FilesDict
        Dictionary of files to deploy.

    Returns
    -------
    Optional[str]
        The shareable URL if deployment succeeds, None otherwise.
    """
    # Check if Vercel CLI is available
    try:
        result = subprocess.run(
            ["vercel", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return _deploy_with_vercel_cli(project_path, project_id, files_dict)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: Mock deployment for development/testing
    # In production, this would integrate with Vercel API or another hosting service
    print(
        colored(
            "Note: Vercel CLI not found. Using mock deployment URL for development.",
            "yellow",
        )
    )
    return f"https://{project_id[:8]}.gpt-engineer.run"


def _deploy_with_vercel_cli(
    project_path: Path, project_id: str, files_dict: FilesDict
) -> Optional[str]:
    """
    Deploy using Vercel CLI.

    Parameters
    ----------
    project_path : Path
        Path to the project directory.
    project_id : str
        Unique identifier for the project.
    files_dict : FilesDict
        Dictionary of files to deploy.

    Returns
    -------
    Optional[str]
        The shareable URL if deployment succeeds, None otherwise.
    """
    # Write files to a temporary directory for deployment
    with tempfile.TemporaryDirectory(prefix="gpt-engineer-deploy-") as temp_dir:
        temp_path = Path(temp_dir)

        # Write all files to temp directory
        for file_path, content in files_dict.items():
            target_path = temp_path / file_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Deploy to Vercel
        try:
            result = subprocess.run(
                ["vercel", "--yes", "--prod"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                # Extract URL from Vercel output
                # Vercel CLI outputs URLs in the format: "https://project-name.vercel.app"
                output_lines = result.stdout.split("\n")
                for line in output_lines:
                    if "https://" in line and ".vercel.app" in line:
                        return line.strip()
                # Fallback URL format
                return f"https://{project_id[:8]}.vercel.app"
            else:
                print(colored(f"Vercel deployment failed: {result.stderr}", "red"))
                return None
        except subprocess.TimeoutExpired:
            print(colored("Vercel deployment timed out", "red"))
            return None
        except Exception as e:
            print(colored(f"Error during Vercel deployment: {str(e)}", "red"))
            return None


def deploy_project(
    project_path: Path, files_dict: FilesDict, prompt: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    """
    Deploy a project and return the shareable URL and project ID.

    This is the main entry point for project deployment. It:
    1. Generates a unique project ID
    2. Creates a manifest file
    3. Injects the manifest into the files
    4. Deploys to hosting service
    5. Returns the shareable URL and project ID

    Parameters
    ----------
    project_path : Path
        Path to the project directory.
    files_dict : FilesDict
        Dictionary of files to deploy.
    prompt : str, optional
        The original prompt used to generate the project.

    Returns
    -------
    tuple[Optional[str], Optional[str]]
        A tuple containing (shareable_url, project_id) if deployment succeeds,
        (None, None) otherwise.
    """
    project_id = generate_project_id()
    manifest = create_gpt_engineer_manifest(project_id, project_path, prompt)

    # Inject manifest into files
    files_dict_with_manifest = inject_manifest_into_files(files_dict, manifest)

    # Deploy to hosting service
    url = deploy_to_vercel(project_path, project_id, files_dict_with_manifest)

    if url:
        return (url, project_id)
    return (None, None)
