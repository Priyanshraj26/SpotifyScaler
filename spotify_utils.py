import os
import subprocess
from pathlib import Path
import streamlit as st
import platform
import dotenv
dotenv.load_dotenv()

def get_spotify_credentials():
    """Get Spotify credentials from environment or Streamlit secrets"""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        client_id = st.secrets["SPOTIFY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIFY_CLIENT_SECRET"]
        return client_id, client_secret
    except:
        # Fall back to environment variables (for local development)
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        return client_id, client_secret

def download_spotify(url, output_dir="./temp"):
    """
    Simple spotDL download that works on Streamlit Cloud.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get credentials
    client_id, client_secret = get_spotify_credentials()
    
    if not client_id or not client_secret:
        st.error("""
        ⚠️ Spotify credentials not found!
        
        For Streamlit Cloud:
        1. Go to your app settings
        2. Add secrets: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
        
        For local development:
        1. Create a .env file with your credentials
        """)
        return False, []
    
    # Build command with credentials
    cmd = [
        "spotdl",
        "download",
        url,
        "--client-id", client_id,
        "--client-secret", client_secret,
        "--output", output_dir,
        "--format", "mp3",
        "--bitrate", "128k"
    ]
    
    try:
        # Run download
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "SPOTIFY_CLIENT_ID": client_id, "SPOTIFY_CLIENT_SECRET": client_secret}
        )
        
        if result.returncode != 0:
            # Try simpler command
            cmd_simple = ["spotdl", url, "--output", output_dir]
            result = subprocess.run(
                cmd_simple,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ, "SPOTIFY_CLIENT_ID": client_id, "SPOTIFY_CLIENT_SECRET": client_secret}
            )
        
        # Find downloaded files
        files = list(Path(output_dir).glob("*.mp3"))
        
        if not files:
            # Check for other formats
            for ext in ['*.m4a', '*.opus', '*.ogg']:
                files.extend(list(Path(output_dir).glob(ext)))
        
        if files:
            return True, files
        else:
            st.error("No files downloaded. The track might be region-restricted or unavailable.")
            return False, []
            
    except subprocess.TimeoutExpired:
        st.error("Download timed out. Please try again.")
        return False, []
    except Exception as e:
        st.error(f"Download error: {str(e)}")
        # Show more detailed error info
        st.info(f"Platform: {platform.system()}")
        st.info(f"Working directory: {os.getcwd()}")
        return False, []