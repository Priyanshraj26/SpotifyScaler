import os
import json
import hashlib
import shutil
import time
from pathlib import Path
from constants import CACHE_DIR

def ensure_directories(*directories):
    """Ensure all required directories exist"""
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def get_file_hash(filepath):
    """Generate MD5 hash of file for caching"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Error hashing file {filepath}: {e}")
        return None

def load_from_cache(file_hash):
    """Load analysis results from cache"""
    if not file_hash:
        return None
    
    cache_file = os.path.join(CACHE_DIR, f"{file_hash}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None
    return None

def save_to_cache(file_hash, results):
    """Save analysis results to cache"""
    if not file_hash:
        return
    
    ensure_directories(CACHE_DIR)
    cache_file = os.path.join(CACHE_DIR, f"{file_hash}.json")
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(results, f)
    except Exception as e:
        print(f"Error saving to cache: {e}")

def clear_cache():
    """Clear all cached results"""
    if os.path.exists(CACHE_DIR):
        try:
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR)
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    return True

def clear_specific_cache(file_hash):
    """Clear cache for a specific file"""
    if not file_hash:
        return False
    
    cache_file = os.path.join(CACHE_DIR, f"{file_hash}.json")
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
            return True
        except Exception as e:
            print(f"Error removing cache file: {e}")
            return False
    return False

def cleanup_temp(dir_path):
    """Safely remove temporary directory with retry logic"""
    if not os.path.exists(dir_path):
        return True
    
    # Try multiple times with delays (Windows file locking issues)
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # First, try to remove all files
            for file_path in Path(dir_path).glob("*"):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
            
            # Then remove the directory
            shutil.rmtree(dir_path)
            return True
            
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(0.5)  # Wait before retry
                continue
            else:
                print(f"Error cleaning up {dir_path} after {max_attempts} attempts: {e}")
                return False
    
    return False

def force_cleanup_temp(dir_path):
    """Force cleanup with OS-specific commands"""
    if not os.path.exists(dir_path):
        return True
    
    try:
        if os.name == 'nt':  # Windows
            os.system(f'rmdir /s /q "{dir_path}"')
        else:  # Unix/Linux/Mac
            os.system(f'rm -rf "{dir_path}"')
        return True
    except Exception as e:
        print(f"Force cleanup failed: {e}")
        return False

def get_cache_info():
    """Get information about cached files"""
    if not os.path.exists(CACHE_DIR):
        return {"count": 0, "size": 0, "files": []}
    
    cache_files = list(Path(CACHE_DIR).glob("*.json"))
    total_size = sum(f.stat().st_size for f in cache_files)
    
    files_info = []
    for f in cache_files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                files_info.append({
                    "hash": f.stem,
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "track": data.get("track", "Unknown"),
                    "artist": data.get("artist", "Unknown")
                })
        except:
            files_info.append({
                "hash": f.stem,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
                "track": "Unknown",
                "artist": "Unknown"
            })
    
    return {
        "count": len(cache_files),
        "size": total_size,
        "files": files_info
    }

def cleanup_old_cache(days=7):
    """Remove cache files older than specified days"""
    if not os.path.exists(CACHE_DIR):
        return 0
    
    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 60 * 60)
    removed_count = 0
    
    for cache_file in Path(CACHE_DIR).glob("*.json"):
        try:
            if cache_file.stat().st_mtime < cutoff_time:
                cache_file.unlink()
                removed_count += 1
        except Exception as e:
            print(f"Error removing old cache file {cache_file}: {e}")
    
    return removed_count

