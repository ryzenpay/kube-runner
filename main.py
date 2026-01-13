import yaml
import subprocess
import time
import os
import logging
logging.basicConfig(level=int(os.getenv("LEVEL", logging.WARNING)))

CONFIG_FILE = "config.yaml"
CACHE_DIR = "./cache"

def run_command(command, cwd=None, input_str=None, silent=False):
    """Utility to run shell commands."""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd=cwd, 
            input=input_str
        )
        if result.returncode != 0 and not silent:
            logging.error(f"Exception executing `{command}`")
            logging.debug(f"Stderr: {result.stderr.strip()}")
        return result
    except Exception as e:
        logging.error(f"Exception: {str(e)}")
        return None

def login_to_registry(registry, token):
    """Authenticates to the container registry."""
    if not token:
        return True
    logging.info(f"🔑 Attempting to login to {registry}...")
    cmd = f"werf cr login {registry} -u kube-runner -p {token}"
    res = run_command(cmd, input_str=token)
    
    if res and res.returncode == 0:
        logging.info("✅ Login successful")
        return True
    else:
        logging.warning("❌ Login failed")
        return False

def get_remote_sha(repo_link, branch="main"):
    cmd = f"git ls-remote {repo_link} refs/heads/{branch}"
    res = run_command(cmd)
    if res and res.returncode == 0 and res.stdout:
        return res.stdout.split()[0]
    return None

def trigger_werf(repo_path, context, registry, repo_name):
    logging.info(f"🚀 Triggering werf build for {repo_name}...")
    build_dir = os.path.join(repo_path, context)
    
    # werf build and push
    # We target registry/repo_name
    cmd = f"werf build --repo {registry}/{repo_name}"
    res = run_command(cmd, cwd=build_dir)
    
    if res and res.returncode == 0:
        logging.info(f"✅ Successfully built and pushed {repo_name}")
    else:
        logging.warning(f"❌ Werf build failed for {repo_name}")

def main():
    logging.info("Starting to monitor repositories...")
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    last_shas = {}

    while True:
        try:
            if not os.path.exists(CONFIG_FILE):
                logging.warning(f"Config file {CONFIG_FILE} not found.")
                time.sleep(10)
                continue

            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
            
            registry = config.get('registry')
            token = os.getenv("registry_token")
            repos = config.get('repos', [])
            interval = config.get('interval_seconds', 60)

            # Handle Login if token exists
            if token:
                login_to_registry(registry, token)

            for repo in repos:
                name = repo['name']
                link = repo['link']
                context = repo.get('context', '.')
                branch = repo.get('branch', 'main')
                
                current_sha = get_remote_sha(link, branch)
                
                if not current_sha:
                    logging.warning(f"⚠️ Could not fetch SHA for {name}. Skipping...")
                    continue

                if name not in last_shas or last_shas[name] != current_sha:
                    logging.info(f"✨ Change detected in {name} ({last_shas.get(name)} -> {current_sha})")
                    
                    local_path = os.path.join(CACHE_DIR, name)
                    
                    if os.path.exists(local_path):
                        run_command(f"git fetch && git reset --hard origin/{branch}", cwd=local_path)
                    else:
                        run_command(f"git clone -b {branch} {link} {local_path}")

                    trigger_werf(local_path, context, registry, name)
                    last_shas[name] = current_sha
                else:
                    logging.debug(f"Checking {name}: No changes.")

        except Exception as e:
            logging.error(f"Critical error: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    main()