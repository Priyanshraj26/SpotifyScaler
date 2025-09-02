import subprocess
import os
from pathlib import Path
import streamlit as st

def download_spotify(url, output_dir):
    """Download audio from Spotify using spotDL"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Build spotDL command
    cmd = [
        "spotdl",
        url,
        "--output", output_dir,
        "--format", "mp3",
        "--bitrate", "128k",  # Low quality for faster download
        "--threads", "4"
    ]
    
    try:
        # Run spotDL
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Find downloaded files
        files = list(Path(output_dir).glob("*.mp3"))
        
        if not files:
            # Check for other audio formats
            for ext in ['*.m4a', '*.opus', '*.ogg']:
                files.extend(list(Path(output_dir).glob(ext)))
        
        return True, files
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        st.error(f"spotDL error: {error_msg}")
        
        # Common error solutions
        if "not found" in error_msg.lower():
            st.info("💡 Make sure spotDL is installed: pip install spotdl")
        elif "404" in error_msg or "not available" in error_msg.lower():
            st.info("💡 This track might not be available. Try a different URL.")
        
        return False, []
    
    except FileNotFoundError:
        st.error("""
        spotDL not found. Please install it:
        ```bash
        pip install spotdl
        ```
        """)
        return False, []

def verify_spotdl_installation():
    """Check if spotDL is properly installed"""
    try:
        result = subprocess.run(
            ["spotdl", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout.strip()
    except:
        return False, None