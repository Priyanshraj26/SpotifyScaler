import os
from pathlib import Path
import streamlit as st
from spotdl import Spotdl
import dotenv
dotenv.load_dotenv()

def download_spotify(url, output_dir="./temp"):
    """
    Download audio from Spotify using SpotDL Python API.
    Handles single tracks and playlists.
    Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in environment.
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            st.error("⚠️ Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.")
            return False, []

        # switch working dir so spotdl saves into output_dir
        cwd_before = os.getcwd()
        os.chdir(output_dir)

        spotdl = Spotdl(client_id=client_id, client_secret=client_secret)

        # Get Song objects from URL
        songs = spotdl.search([url])
        if not songs:
            st.error("⚠️ No songs found for this URL.")
            os.chdir(cwd_before)
            return False, []

        files = []
        for song in songs:
            downloaded = spotdl.download(song)

            # Some versions return tuple, some return Song
            if isinstance(downloaded, tuple):
                downloaded = downloaded[0]

            # If it's a Song object, get the download_path
            if hasattr(downloaded, "download_path"):
                path = downloaded.download_path
            elif isinstance(downloaded, (str, Path)):
                path = downloaded
            else:
                path = None

            # Ensure path is a string or Path and exists
            if path and os.path.exists(str(path)):
                files.append(Path(path))

        os.chdir(cwd_before)

        if not files:
            st.error("⚠️ No MP3s saved. Check the link.")
            return False, []

        return True, files

    except Exception as e:
        st.error(f"spotDL error: {e}")