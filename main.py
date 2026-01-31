import yaml
import subprocess
import time
import os
import logging
import git
import json
import tempfile
import sys

# Configure logging
logging.basicConfig(
    level=int(os.getenv("LEVEL", logging.INFO)),
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

CONFIG_PATH = "config.yaml"
DOCKER_CONFIG_PATH = os.path.join(os.path.expanduser("~/.docker"), "config.json")

def setup_auth(registry_url: str):
    username = os.environ.get("REGISTRY_USERNAME")
    password = os.environ.get("REGISTRY_PASSWORD")

    if not username or not password:
        logging.warning("⚠️  CI_REGISTRY_USER or CI_REGISTRY_PASSWORD not set. Push might fail.")
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
    
    logging.info(f"🔐 Configured credentials for {registry_url}")

def get_remote_sha(repo_url: str, branch: str) -> str | None:
    """Gets the latest commit SHA from the remote without cloning."""
    g = git.cmd.Git()
    try:
        refs = g.ls_remote(repo_url, branch).split('\n')
        if refs and refs[0]:
            return refs[0].split('\t')[0][:7] # Return short SHA
    except git.exc.GitCommandError as e:
        logging.error(f"❌ Failed to check remote SHA for {repo_url}: {e}")
    return None

def run_build(repo_conf: dict, registry_base: str, build_state: dict):
    name = repo_conf['name']
    git_link = repo_conf['link']
    branch = repo_conf.get('branch', 'main')
    
    # 1. Check if update is needed
    logging.info(f"🔎 Checking {name} ({branch})...")
    remote_sha = get_remote_sha(git_link, branch)

    if not remote_sha:
        logging.warning(f"⚠️  Could not retrieve SHA for {name}, skipping...")
        return

    last_built_sha = build_state.get(name)

    if last_built_sha == remote_sha:
        logging.info(f"💤 No changes detected for {name} ({remote_sha}). Skipping build.")
        return

    logging.info(f"🚀 Changes detected for {name}! (Old: {last_built_sha} -> New: {remote_sha})")
    
    image_base = f"{registry_base}/{name}"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = os.path.join(temp_dir, name)
        
        try:
            # 2. Clone Repository
            logging.info(f"📥 Cloning {name}...")
            git.Repo.clone_from(
                git_link, 
                repo_dir, 
                branch=branch, 
                depth=1
            )
            
            logging.info(f"🏗️  Building {name}:{remote_sha}...")

            cmd = [
                "buildctl-daemonless.sh", "build",
                "--frontend", "dockerfile.v0",
                "--local", f"context={repo_dir}",
                "--local", f"dockerfile={repo_dir}",
                "--import-cache", f"type=registry,ref={image_base}:buildcache",
                "--export-cache", f"type=registry,ref={image_base}:buildcache",
                # Tag with latest AND the specific commit SHA
                "--output", f"type=image,name={image_base}:latest,{image_base}:{remote_sha},push=true"
            ]

            # 3. Execute Build
            subprocess.run(cmd, check=True)
            
            logging.info(f"✅ Successfully built and pushed {name}:{remote_sha}")
            
            # 4. Update state only on success
            build_state[name] = remote_sha

        except git.exc.GitCommandError as e:
            logging.error(f"❌ Git operation failed for {name}: {e}")
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Build failed for {name}. Exit code: {e.returncode}")
        except Exception as e:
            logging.error(f"💥 An unexpected error occurred for {name}: {e}")

def main():
    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"⛔ Config file not found at {CONFIG_PATH}")
        sys.exit(1)

    logging.info("🤖 Starting BuildKit Runner...")

    # { 'repo_name': 'sha123' }
    build_state = {}

    while True:
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)

            registry = config.get('registry').replace("http://", "").replace("https://", "")
            interval = config.get('interval_seconds', 60)
            repos = config.get('repos', [])

            setup_auth(registry)

            for repo in repos:
                run_build(repo, registry, build_state)

            logging.debug(f"⏳ Sleeping for {interval} seconds...")
            time.sleep(interval)

        except KeyboardInterrupt:
            logging.info("👋 Stopping BuildKit Runner.")
            sys.exit(0)
        except Exception as e:
            logging.error(f"💥 Global Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()