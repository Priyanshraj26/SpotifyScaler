import os
import subprocess
from pathlib import Path

def download_spotify(url, output_dir="./temp"):
    """Minimal spotDL download."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Change to output directory before downloading
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        subprocess.run(["spotdl", "download", url], capture_output=True)
        files = list(Path(".").glob("*.mp3"))
        return True, [Path(output_dir) / f for f in files]
    except:
        return False, []
    finally:
        os.chdir(original_dir)
