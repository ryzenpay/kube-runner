import yaml
import subprocess
import time
import os
import logging
import git
import json
import tempfile
import sys

logging.basicConfig(level=int(os.getenv("LEVEL", logging.WARNING)))

CONFIG_PATH = "config.yml"
DOCKER_CONFIG_PATH = os.path.join(os.path.expanduser("~/.docker"), "config.json")

def setup_auth(registry_url: str):
    username = os.environ.get("REGISTRY_USERNAME")
    password = os.environ.get("REGISTRY_PASSWORD")

    if not username or not password:
        logging.warning("CI_REGISTRY_USER or CI_REGISTRY_PASSWORD not set. Push might fail.")
        return

    # Ensure .docker directory exists
    os.makedirs(os.path.expanduser("~/.docker"), exist_ok=True)

    config_data = {
        "auths": {
            registry_url: {
                "username": username,
                "password": password
            }
        }
    }

    with open(DOCKER_CONFIG_PATH, 'w') as f:
        json.dump(config_data, f)
    
    logging.info(f"Configured credentials for {registry_url}")


def run_build(repo_conf: dict, registry_base):
    name = repo_conf['name']
    git_link = repo_conf['link']
    branch = repo_conf.get('branch', 'main')
    
    image_base = f"{registry_base}/{name}"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = os.path.join(temp_dir, name)
        
        try:
            # 1. Clone Repository using GitPython
            logging.info(f"Cloning {name} (branch: {branch})...")
            repo = git.Repo.clone_from(
                git_link, 
                repo_dir, 
                branch=branch, 
                depth=1
            )
            
            # 2. Get Commit Hash (short 7-character hash)
            commit_sha = repo.head.commit.hexsha[:7]
            
            logging.info(f"Building {name}:{commit_sha}...")

            cmd = [
                "buildctl-daemonless.sh", "build",
                "--frontend", "dockerfile.v0",
                "--local", f"context={repo_dir}",
                "--local", f"dockerfile={repo_dir}",
                "--import-cache", f"type=registry,ref={image_base}:buildcache",
                "--export-cache", f"type=registry,ref={image_base}:buildcache",
                "--output", f"type=image,name={image_base}:latest,push=true"
            ]

            # 4. Execute Build
            subprocess.run(cmd, check=True)
            
            logging.info(f"Successfully built and pushed {name}")

        except git.exc.GitCommandError as e:
            logging.error(f"Git operation failed for {name}: {e}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Build failed for {name}. Exit code: {e.returncode}")
        except Exception as e:
            logging.error(f"An unexpected error occurred for {name}: {e}")

def main():
    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Config file not found at {CONFIG_PATH}")
        sys.exit(1)

    logging.info("Starting BuildKit Runner...")

    while True:
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)

            registry = config.get('registry').replace("http://", "").replace("https://", "")
            interval = config.get('interval_seconds', 60)
            repos = config.get('repos', [])

            setup_auth(registry)

            for repo in repos:
                run_build(repo, registry)

            logging.debug(f"Sleeping for {interval} seconds...")
            time.sleep(interval)

        except Exception as e:
            logging.error(f"{e}")
            time.sleep(60)

if __name__ == "__main__":
    main()