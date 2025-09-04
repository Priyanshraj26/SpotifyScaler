import streamlit as st
import os
import pandas as pd
from datetime import datetime

# Import all modules
from constants import TEMP_DIR, UPLOAD_DIR, CACHE_DIR, SUPPORTED_AUDIO_FORMATS
from cache_utils import cleanup_temp, ensure_directories
from spotify_utils import download_spotify
from analysis import detect_key_librosa, analyze_files, calculate_key_transitions
from visualization import create_visualizations, create_key_transition_chart
from export import export_to_csv, export_to_excel, export_to_json
from ui_components import (
    display_disclaimer, display_sidebar_settings, display_overview_tab,
    display_detailed_results_tab, display_export_tab
)

# Page config
st.set_page_config(
    page_title="Spotify Key Analyzer",
    page_icon="🎵",
    layout="wide"
)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'temp_files' not in st.session_state:
    st.session_state.temp_files = []

def handle_file_upload(use_cache, auto_cleanup):
    """Handle audio file upload"""
    st.header("Upload Audio File")
    
    uploaded_file = st.file_uploader(
        "Choose an audio file",
        type=SUPPORTED_AUDIO_FORMATS,
        help=f"Supported formats: {', '.join(SUPPORTED_AUDIO_FORMATS).upper()}"
    )
    
    if uploaded_file is not None:
        # Save uploaded file
        ensure_directories(UPLOAD_DIR)
        filepath = os.path.join(UPLOAD_DIR, uploaded_file.name)
        
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"Uploaded: {uploaded_file.name}")
        
        if st.button("Analyze", type="primary"):
            with st.spinner("Analyzing audio..."):
                # Analyze single file
                metadata = {"artist": "User Upload", "track": uploaded_file.name}
                analysis = detect_key_librosa(filepath, use_cache=use_cache)
                
                # Create results dataframe
                results_df = pd.DataFrame([{
                    "file": uploaded_file.name,
                    "artist": metadata["artist"],
                    "track": metadata["track"],
                    **analysis
                }])
                
                st.session_state.analysis_results = results_df
                
                # Cleanup if enabled
                if auto_cleanup:
                    cleanup_temp(UPLOAD_DIR)
                
                st.rerun()

def handle_spotify_input(input_mode, use_cache, auto_cleanup):
    """Handle Spotify URL input"""
    st.header(f"Analyze {input_mode}")
    
    spotify_url = st.text_input(
        "Enter Spotify URL:",
        placeholder="https://open.spotify.com/track/... or https://open.spotify.com/playlist/..."
    )
    
    if st.button("Download & Analyze", type="primary") and spotify_url:
        # Cleanup previous temp files
        cleanup_temp(TEMP_DIR)
        
        # Download progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Download from Spotify
            status_text.text("Downloading from Spotify...")
            success, files = download_spotify(spotify_url, TEMP_DIR)
            
            if success and files:
                st.success(f"Downloaded {len(files)} file(s)")
                
                # Analyze files
                status_text.text("Analyzing audio files...")
                
                def update_progress(current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"Analyzing file {current + 1} of {total}...")
                
                results_df = analyze_files(files, progress_callback=update_progress, use_cache=use_cache)
                
                st.session_state.analysis_results = results_df
                st.session_state.temp_files = files
                
                progress_bar.progress(1.0)
                status_text.text("Analysis complete!")
                
                # Cleanup if auto-cleanup is enabled
                if auto_cleanup:
                    cleanup_temp(TEMP_DIR)
                    st.session_state.temp_files = []
                
                st.rerun()
                
            else:
                st.error("Failed to download audio. Please check the URL and try again.")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

def display_results(confidence_threshold, show_alternatives):
    """Display analysis results"""
    df = st.session_state.analysis_results
    
    st.markdown("---")
    st.header("Analysis Results")
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Visualizations", "🎵 Detailed Results", "💾 Export"])
    
    with tab1:
        display_overview_tab(df)
    
    with tab2:
        display_visualizations_tab(df)
    
    with tab3:
        display_detailed_results_tab(df, confidence_threshold, show_alternatives)
    
    with tab4:
        # Prepare export data
        csv_data = export_to_csv(df)
        excel_data = export_to_excel(df)
        json_data = export_to_json(df)
        
        display_export_tab(df, csv_data, excel_data, json_data)
        
        # Cleanup option
        if st.session_state.temp_files:
            st.warning(f"⚠️ {len(st.session_state.temp_files)} temporary files still in memory")
            if st.button("🗑️ Clean Temporary Files", type="secondary"):
                cleanup_temp(TEMP_DIR)
                st.session_state.temp_files = []
                st.success("Temporary files cleaned!")

def display_visualizations_tab(df):
    """Display visualization charts"""
    # Create visualizations
    fig_keys, fig_mode, fig_tempo, fig_conf = create_visualizations(df)
    
    # Display charts
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig_keys, use_container_width=True)
        st.plotly_chart(fig_tempo, use_container_width=True)
    
    with col2:
        st.plotly_chart(fig_mode, use_container_width=True)
        st.plotly_chart(fig_conf, use_container_width=True)

    
    # Additional analysis for playlists
    if len(df) > 2:
        st.subheader("Advanced Analysis")
        st.write("**Key Transitions in Playlist Order:**")
        
        transitions_df = calculate_key_transitions(df)
        fig_trans = create_key_transition_chart(transitions_df)
        st.plotly_chart(fig_trans, use_container_width=True)

def main():
    """Main application function"""
    st.title("🎵 Spotify Key Analyzer")
    st.markdown("Analyze musical keys and scales using spotDL + librosa")
    
    # Display disclaimer
    display_disclaimer()
    
    # Get ALL sidebar settings (now returns 5 values)
    input_mode, use_cache, auto_cleanup, confidence_threshold, show_alternatives = display_sidebar_settings()
    
    # Manual cleanup button in sidebar
    with st.sidebar:
        if st.button("🗑️ Clean All Temp Files"):
            cleanup_temp(TEMP_DIR)
            cleanup_temp(UPLOAD_DIR)
            st.success("Cleaned up temporary files!")
    
    # Main content based on input mode
    if input_mode == "Upload Audio File":
        handle_file_upload(use_cache, auto_cleanup)
    else:
        handle_spotify_input(input_mode, use_cache, auto_cleanup)
    
    # Display results if available - pass the settings as parameters
    if st.session_state.analysis_results is not None:
        display_results(confidence_threshold, show_alternatives)

if __name__ == "__main__":
    # Ensure directories exist
    ensure_directories(TEMP_DIR, UPLOAD_DIR, CACHE_DIR)
    main()