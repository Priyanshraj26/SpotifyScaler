import os
import json
import hashlib
import shutil
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

def cleanup_temp(dir_path):
    """Safely remove temporary directory"""
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            return True
        except Exception as e:
            print(f"Error cleaning up {dir_path}: {e}")
            return False
    return True