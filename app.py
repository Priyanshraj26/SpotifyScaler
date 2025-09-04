import streamlit as st
import os
import pandas as pd
from datetime import datetime

# Import all modules
from constants import TEMP_DIR, UPLOAD_DIR, CACHE_DIR, SUPPORTED_AUDIO_FORMATS
from cache_utils import (
    cleanup_temp, ensure_directories, force_cleanup_temp, 
    get_file_hash, clear_specific_cache, get_cache_info
)
from spotify_utils import download_spotify
from analysis import detect_key_librosa, analyze_files, calculate_key_transitions
from visualization import create_visualizations, create_key_transition_chart
from export import export_to_csv, export_to_excel, export_to_json
from ui_components import (
    display_disclaimer, display_sidebar_settings, display_overview_tab,
    display_detailed_results_tab, display_export_tab
)

# Page config with Spotify theme
st.set_page_config(
    page_title="Spotify Scaler",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Spotify-like theme
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    
    /* Sidebar */
    .css-1d391kg, .css-1avcm0n {
        background-color: #000000;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #E7E7E7 !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #1DB954;
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #1ED760;
        transform: scale(1.05);
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background-color: #1DB954;
        color: black;
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background-color: #282828;
        color: #FFFFFF;
    }
    
    /* Input fields */
    .stTextInput > div > div > input {
        background-color: #282828;
        color: #FFFFFF;
        border: 1px solid #282828;
        border-radius: 4px;
    }
    
    /* Selectbox and multiselect */
    .stSelectbox > div > div, .stMultiSelect > div > div {
        background-color: #282828;
        color: #FFFFFF;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background-color: #181818;
        padding: 10px;
        border-radius: 8px;
    }
    
    /* Metrics */
    [data-testid="metric-container"] {
        background-color: #282828;
        border: 1px solid #282828;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Dataframe */
    .dataframe {
        background-color: #282828;
        color: #FFFFFF;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #181818;
        border-radius: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: #B3B3B3;
        background-color: transparent;
    }
    
    .stTabs [aria-selected="true"] {
        color: #FFFFFF;
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background-color: #1DB954;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #282828;
        color: #FFFFFF;
        border-radius: 8px;
    }
    
    /* Success messages */
    .stSuccess {
        background-color: #1DB954;
        color: #000000;
    }
    
    /* Warning messages */
    .stWarning {
        background-color: #FFA500;
        color: #000000;
    }
    
    /* Error messages */
    .stError {
        background-color: #F44336;
        color: #FFFFFF;
    }
    
    /* File uploader */
    .stFileUploader > div {
        background-color: #282828;
        margin-top: 20px;
    }
    
    /* Slider */
    .stSlider > div > div > div {

    }
    
    /* Download button special */
    [data-testid="stDownloadButton"] > button {
        background-color: #1DB954;
        color: black;
        border: none;
        border-radius: 20px;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #282828;
        color: #FFFFFF;
        border-left: 4px solid #1DB954;
    }
    
    /* Plotly charts background */
    .js-plotly-plot {
        background-color: #181818 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'temp_files' not in st.session_state:
    st.session_state.temp_files = []

def handle_file_upload(use_cache, auto_cleanup):
    """Handle audio file upload"""
    st.header("Upload Audio File")
    
    # Create upload container with Spotify styling
    with st.container():
        uploaded_file = st.file_uploader(
            "Drop your audio file here or click to browse",
            type=SUPPORTED_AUDIO_FORMATS,
            help=f"Supported formats: {', '.join(SUPPORTED_AUDIO_FORMATS).upper()}"
        )
    
    if uploaded_file is not None:
        # Save uploaded file
        ensure_directories(UPLOAD_DIR)
        filepath = os.path.join(UPLOAD_DIR, uploaded_file.name)
        
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
        
        if analyze_btn:
            with st.spinner("Analyzing audio..."):
                # Clear old cache if not using cache
                if not use_cache:
                    file_hash = get_file_hash(filepath)
                    clear_specific_cache(file_hash)
                
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
                    if not cleanup_temp(UPLOAD_DIR):
                        force_cleanup_temp(UPLOAD_DIR)
                
                st.rerun()

def handle_spotify_input(input_mode, use_cache, auto_cleanup):
    """Handle Spotify URL input"""
    st.header(f"🎵 Analyze {input_mode}")
    
    # Spotify-styled input
    spotify_url = st.text_input(
        "Enter Spotify URL:",
        placeholder="https://open.spotify.com/track/... or https://open.spotify.com/playlist/...",
        help="Paste a Spotify track or playlist URL"
    )
    
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        analyze_btn = st.button("🎵 Download & Analyze", type="primary", use_container_width=True)
    
    if analyze_btn and spotify_url:
        # Cleanup previous temp files
        cleanup_temp(TEMP_DIR)
        
        # Progress container
        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        try:
            # Download from Spotify
            status_text.text("🎵 Connecting to Spotify...")
            progress_bar.progress(0.1)
            
            success, files = download_spotify(spotify_url, TEMP_DIR)
            
            if success and files:
                progress_bar.progress(0.5)
                st.success(f"✅ Downloaded {len(files)} file(s)")
                
                # Analyze files
                status_text.text("🔍 Analyzing audio files...")
                
                def update_progress(current, total):
                    progress = 0.5 + (current / total) * 0.5
                    progress_bar.progress(progress)
                    status_text.text(f"🎵 Analyzing track {current + 1} of {total}...")
                
                results_df = analyze_files(files, progress_callback=update_progress, use_cache=use_cache)
                
                st.session_state.analysis_results = results_df
                st.session_state.temp_files = files
                
                progress_bar.progress(1.0)
                status_text.text("✅ Analysis complete!")
                
                # Cleanup if auto-cleanup is enabled
                if auto_cleanup:
                    if not cleanup_temp(TEMP_DIR):
                        force_cleanup_temp(TEMP_DIR)
                    st.session_state.temp_files = []
                
                st.rerun()
                
            else:
                st.error("❌ Failed to download audio. Please check the URL and try again.")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

def display_results(confidence_threshold, show_alternatives):
    """Display analysis results with Spotify styling"""
    df = st.session_state.analysis_results
    
    st.markdown("---")
    
    # Results header with Spotify green
    st.markdown("""
        <h2 style='color: #1DB954; margin-bottom: 20px;'>
            Analysis Results
        </h2>
    """, unsafe_allow_html=True)
    
    # Create styled tabs
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
        
        # Cleanup option with Spotify styling
        if st.session_state.temp_files:
            st.markdown("---")
            st.warning(f"⚠️ {len(st.session_state.temp_files)} temporary files still in memory")
            
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                if st.button("🗑️ Clean Temp Files", type="secondary", use_container_width=True):
                    if cleanup_temp(TEMP_DIR):
                        st.session_state.temp_files = []
                        st.success("✅ Temporary files cleaned!")
                        st.rerun()
                    else:
                        force_cleanup_temp(TEMP_DIR)
                        st.session_state.temp_files = []
                        st.success("✅ Temporary files force cleaned!")
                        st.rerun()

def display_visualizations_tab(df):
    """Display visualization charts with Spotify theme"""
    # Create visualizations
    fig_keys, fig_mode, fig_tempo, fig_conf= create_visualizations(df)
    
    # Update chart colors to match Spotify theme
    spotify_colors = {
        'bg': '#181818',
        'grid': '#282828',
        'text': '#FFFFFF',
        'primary': '#1DB954',
        'secondary': '#1ED760'
    }
    
    # Apply Spotify theme to all charts
    for fig in [fig_keys, fig_mode, fig_tempo, fig_conf]:
        fig.update_layout(
            plot_bgcolor=spotify_colors['bg'],
            paper_bgcolor=spotify_colors['bg'],
            font_color=spotify_colors['text'],
            title_font_color=spotify_colors['primary'],
            title_font_size=20,
            showlegend=True,
            legend=dict(
                bgcolor=spotify_colors['grid'],
                bordercolor=spotify_colors['primary'],
                borderwidth=1
            )
        )
        fig.update_xaxes(gridcolor=spotify_colors['grid'])
        fig.update_yaxes(gridcolor=spotify_colors['grid'])
    
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
        st.subheader("🎵 Advanced Analysis")
        st.write("**Key Transitions in Playlist Order:**")
        
        transitions_df = calculate_key_transitions(df)
        fig_trans = create_key_transition_chart(transitions_df)
        
        # Apply Spotify theme
        fig_trans.update_layout(
            plot_bgcolor=spotify_colors['bg'],
            paper_bgcolor=spotify_colors['bg'],
            font_color=spotify_colors['text'],
            title_font_color=spotify_colors['primary']
        )
        
        st.plotly_chart(fig_trans, use_container_width=True)

def main():
    """Main application function"""
    # Title with Spotify styling
    st.markdown("""
        <h1 style='text-align: center; color: #b3b3b3; font-size: 3em; margin-bottom: 0;'>
             🎵 Spotify Scaler
        </h1>
        <p style='text-align: center; color: #B3B3B3; font-size: 1.2em;'> Analyze musical keys,scales and tempo using spotDL + librosa
        </p>
    """, unsafe_allow_html=True)
    
    # Display disclaimer
    display_disclaimer()
    
    # Get ALL sidebar settings (now returns 5 values)
    input_mode, use_cache, auto_cleanup, confidence_threshold, show_alternatives = display_sidebar_settings()
    
    # Manual cleanup button in sidebar with Spotify styling
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🧹 Cleanup Options")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clean Temp", use_container_width=True):
                if cleanup_temp(TEMP_DIR) and cleanup_temp(UPLOAD_DIR):
                    st.success("✅ Temp cleaned!")
                else:
                    force_cleanup_temp(TEMP_DIR)
                    force_cleanup_temp(UPLOAD_DIR)
                    st.success("✅ Force cleaned!")
        
        with col2:
            # Show cache size
            cache_info = get_cache_info()
            if cache_info['count'] > 0:
                st.metric("Cache Files", cache_info['count'])
    
    # Main content area with Spotify-style container
    main_container = st.container()
    
    with main_container:
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Main content based on input mode
        if input_mode == "Upload Audio File":
            handle_file_upload(use_cache, auto_cleanup)
        else:
            handle_spotify_input(input_mode, use_cache, auto_cleanup)
    
    # Display results if available
    if st.session_state.analysis_results is not None:
        display_results(confidence_threshold, show_alternatives)
    
    # Footer with Spotify styling
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #B3B3B3; padding: 20px;'>
            <p>Made with ❤️ using SpotDL and Librosa | 
            <a href='https://github.com/Priyanshraj26/SpotifyScaler' style='color: #b3b3b3;'>GitHub</a> |
            <a href='https://portfolio-website-puce-ten.vercel.app/' style='color: #b3b3b3;'>Portfolio</a>
            </p>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    # Ensure directories exist
    ensure_directories(TEMP_DIR, UPLOAD_DIR, CACHE_DIR)
    
    # Set page title in browser tab
    st.markdown("""
        <script>
            document.title = "Spotify Scaler 🎵"
        </script>
    """, unsafe_allow_html=True)
    
    main()