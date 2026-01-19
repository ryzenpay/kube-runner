import yaml
import subprocess
import time
import os
import logging
import git
logging.basicConfig(level=int(os.getenv("LEVEL", logging.WARNING)))

CONFIG_FILE = "config.yaml"
CACHE_DIR = "./cache"

def run_command(command, cwd=None, silent=False):
    """Utility to run shell commands."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd=cwd,
            env=os.environ.copy()
        )
        if result.returncode != 0 and not silent:
            logging.error(f"💥 Exception executing `{command}`")
            logging.debug(f"Stderr: {result.stderr.strip()}")
        return result
    except Exception as e:
        logging.error(f"💥 Exception: {str(e)}")
        return None

def login_to_registry(registry, username, password):
    logging.info(f"🔑 Attempting to login to {registry}...")
    cmd = f"podman login --tls-verify=false -u {username} -p {password} {registry}"
    res = run_command(cmd)
    
    if res and res.returncode == 0:
        logging.info("✅ Login successful")
        return True
    else:
        logging.warning("❌ Login failed")
        return False

def get_repo_sha(path):
    try:
        repo = git.Repo(path=path, search_parent_directories=True)
        return repo.head.object.hexsha
    except Exception as e:
        logging.error(f"⚠️ Error getting SHA for {path}: {e}")
        return None

def trigger_build(path, name, registry):
    logging.info(f"🚀 Triggering build for {name}...")
    
    cmd = f"podman build --tag {registry}/{name} ."
    res = run_command(cmd, cwd=path)
    
    if res and res.returncode == 0:
        logging.info(f"✅ Successfully built and pushed {name}")
    else:
        logging.warning(f"❌ build failed for {name}")

def main():
    logging.info("👀 Starting to monitor repositories...")
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    last_shas = {}
    interval = 60

    while True:
        try:
            if not os.path.exists(CONFIG_FILE):
                logging.warning(f"⚠️ Config file {CONFIG_FILE} not found. Waiting...")
                time.sleep(10)
                continue

            with open(CONFIG_FILE, 'r') as f:
                config: dict = yaml.safe_load(f)
            
            registry = config.get('registry')
            repos = config.get('repos', [])
            interval = int(config.get('interval_seconds', 60))

            login_to_registry(registry, os.getenv("REGISTRY_USERNAME"), os.getenv("REGISTRY_PASSWORD"))

            for repo in repos:
                name = repo['name']
                link = repo['link']
                branch = repo.get('branch', 'main')
                
                path = os.path.join(CACHE_DIR, name)

                if not os.path.exists(path):
                    logging.info(f"📥 Initially cloning repo {name} ({branch})...")
                    git.Repo.clone_from(link, to_path=path, branch=branch)
                else:
                    repo = git.Repo(path=path)
                    logging.debug(f"🔄 Pulling {name}...")
                    repo.remotes.origin.pull()

                current_sha = get_repo_sha(path)
                
                if not current_sha:
                    logging.warning(f"⚠️ Could not fetch SHA for {name}. Skipping...")
                    continue

                if name not in last_shas:
                    logging.info(f"🏃 Starting first build for {name} ({current_sha})")
                    trigger_build(path, name, registry)
                elif last_shas[name] != current_sha:
                    logging.info(f"✨ Change detected in {name} ({last_shas.get(name)} -> {current_sha})")
                    trigger_build(path, name, registry)
                    last_shas[name] = current_sha

        except Exception as e:
            logging.error(f"Loop error: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    main()