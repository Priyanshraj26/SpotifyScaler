import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict
import os
from dotenv import load_dotenv
import base64
from io import BytesIO
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import time

# Load environment variables
load_dotenv()

# Musical scale mapping
PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Relative scale mapping (Major -> Minor)
RELATIVE_SCALES = {
    'C Major': 'A Minor',
    'C# Major': 'A# Minor',
    'D Major': 'B Minor',
    'D# Major': 'C Minor',
    'E Major': 'C# Minor',
    'F Major': 'D Minor',
    'F# Major': 'D# Minor',
    'G Major': 'E Minor',
    'G# Major': 'F Minor',
    'A Major': 'F# Minor',
    'A# Major': 'G Minor',
    'B Major': 'G# Minor'
}

# Reverse mapping for easy lookup
RELATIVE_SCALES_REVERSE = {v: k for k, v in RELATIVE_SCALES.items()}

def init_spotify():
    """Initialize Spotify client"""
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        st.error("""
        ⚠️ **Spotify API credentials not found!**
        
        Please set up your credentials in Streamlit Cloud:
        1. Go to your app settings
        2. Navigate to Secrets
        3. Add:
        ```
        SPOTIFY_CLIENT_ID = "your_client_id_here"
        SPOTIFY_CLIENT_SECRET = "your_client_secret_here"
        ```
        """)
        return None
    
    try:
        # Use a longer timeout
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Create client with custom settings
        sp = spotipy.Spotify(
            client_credentials_manager=client_credentials_manager,
            requests_timeout=10,
            retries=3
        )
        
        return sp
        
    except Exception as e:
        st.error(f"""
        ⚠️ **Failed to authenticate with Spotify!**
        
        Error: {str(e)}
        """)
        return None

def extract_playlist_id(url):
    """Extract playlist ID from Spotify URL"""
    if 'playlist/' in url:
        return url.split('playlist/')[1].split('?')[0]
    return None

def get_scale_name(key, mode):
    """Convert key number and mode to scale name"""
    if key == -1:  # No key detected
        return "Unknown"
    pitch = PITCH_CLASSES[key]
    scale_type = 'Major' if mode == 1 else 'Minor'
    return f"{pitch} {scale_type}"

def get_relative_group(scale_name):
    """Get the relative scale group for a given scale"""
    if scale_name == "Unknown":
        return "Unknown"
    if scale_name in RELATIVE_SCALES:
        return f"{scale_name} ↔ {RELATIVE_SCALES[scale_name]}"
    elif scale_name in RELATIVE_SCALES_REVERSE:
        return f"{RELATIVE_SCALES_REVERSE[scale_name]} ↔ {scale_name}"
    return scale_name

def fetch_audio_features_single(sp, track_id):
    """Fetch audio features for a single track with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            features = sp.audio_features([track_id])
            if features and features[0]:
                return features[0]
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                continue
            return None

def fetch_playlist_data(sp, playlist_id):
    """Fetch playlist tracks and their audio features"""
    tracks_data = []
    
    try:
        # Get playlist info first
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist['name']
        total_tracks = playlist['tracks']['total']
        
        st.info(f"Fetching {total_tracks} tracks from '{playlist_name}'...")
        
        # Get playlist tracks
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        # Filter valid tracks
        valid_tracks = []
        for track in tracks:
            if (track.get('track') and 
                track['track'].get('id') and 
                not track.get('is_local', False) and
                track['track'].get('type') == 'track'):
                valid_tracks.append(track)
        
        if not valid_tracks:
            st.warning("No valid tracks found in the playlist")
            return pd.DataFrame()
        
        st.info(f"Processing {len(valid_tracks)} valid tracks...")
        
        # Progress tracking
        progress_bar = st.progress(0)
        progress_text = st.empty()
        successful_tracks = 0
        failed_tracks = 0
        
        # Process tracks individually to handle 403 errors better
        for idx, track_item in enumerate(valid_tracks):
            track = track_item['track']
            track_id = track['id']
            
            # Update progress
            progress = (idx + 1) / len(valid_tracks)
            progress_bar.progress(progress)
            progress_text.text(f"Processing: {idx + 1}/{len(valid_tracks)} tracks (Success: {successful_tracks}, Failed: {failed_tracks})")
            
            # Try to get audio features
            features = fetch_audio_features_single(sp, track_id)
            
            if features:
                tracks_data.append({
                    'name': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'key': features.get('key', -1),
                    'mode': features.get('mode', 0),
                    'scale': get_scale_name(
                        features.get('key', -1),
                        features.get('mode', 0)
                    ),
                    'tempo': features.get('tempo', 0),
                    'energy': features.get('energy', 0),
                    'valence': features.get('valence', 0)
                })
                successful_tracks += 1
            else:
                # Add track without audio features
                tracks_data.append({
                    'name': track['name'],
                    'artist': ', '.join([artist['name'] for artist in track['artists']]),
                    'key': -1,
                    'mode': 0,
                    'scale': 'Unknown',
                    'tempo': 0,
                    'energy': 0,
                    'valence': 0
                })
                failed_tracks += 1
            
            # Small delay to avoid rate limiting
            if idx % 10 == 0:
                time.sleep(0.1)
        
        # Clear progress indicators
        progress_bar.empty()
        progress_text.empty()
        
        if not tracks_data:
            st.error("Could not retrieve any track data")
            return pd.DataFrame()
        
        # Show summary
        if failed_tracks > 0:
            st.warning(f"""
            ⚠️ Partial data retrieved:
            - Successfully analyzed: {successful_tracks} tracks
            - Failed to analyze: {failed_tracks} tracks
            
            Some tracks may show as "Unknown" scale due to API limitations.
            """)
        else:
            st.success(f"✅ Successfully analyzed all {successful_tracks} tracks!")
        
        return pd.DataFrame(tracks_data)
        
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 404:
            st.error("Playlist not found. Please check the URL and make sure it's a public playlist.")
        elif e.http_status == 401:
            st.error("Authentication failed. Please check your Spotify credentials.")
        else:
            st.error(f"Spotify API error ({e.http_status}): {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return pd.DataFrame()

def create_distribution_charts(df, classification_type):
    """Create distribution charts for scales"""
    # Filter out unknown scales for visualization
    df_known = df[df['scale'] != 'Unknown'].copy()
    
    if df_known.empty:
        st.warning("No tracks with detected scales found")
        return None, None, None
    
    if classification_type == "Relative Classification":
        df_known['group'] = df_known['scale'].apply(get_relative_group)
        scale_counts = df_known['group'].value_counts()
    else:
        scale_counts = df_known['scale'].value_counts()
    
    # Bar chart
    fig_bar = px.bar(
        x=scale_counts.index,
        y=scale_counts.values,
        labels={'x': 'Scale', 'y': 'Number of Songs'},
        title='Songs per Scale Distribution',
        color=scale_counts.values,
        color_continuous_scale='viridis'
    )
    fig_bar.update_xaxis(tickangle=-45)
    fig_bar.update_layout(showlegend=False)
    
    # Pie chart
    fig_pie = px.pie(
        values=scale_counts.values,
        names=scale_counts.index,
        title='Scale Distribution (Percentage)'
    )
    
    # Major vs Minor ratio
    major_count = df_known[df_known['mode'] == 1].shape[0]
    minor_count = df_known[df_known['mode'] == 0].shape[0]
    
    fig_ratio = go.Figure(data=[
        go.Bar(name='Major', x=['Scale Type'], y=[major_count], marker_color='#FF6B6B'),
        go.Bar(name='Minor', x=['Scale Type'], y=[minor_count], marker_color='#4ECDC4')
    ])
    fig_ratio.update_layout(
        title='Major vs Minor Distribution',
        barmode='group',
        showlegend=True
    )
    
    return fig_bar, fig_pie, fig_ratio

def export_to_excel(df):
    """Export data to Excel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name='Playlist Analysis', index=False)
        
        # Summary sheet
        df_known = df[df['scale'] != 'Unknown']
        summary_df = pd.DataFrame({
            'Metric': ['Total Songs', 'Songs with Scale Data', 'Songs without Scale Data', 'Major Songs', 'Minor Songs', 'Most Common Scale'],
            'Value': [
                len(df),
                len(df_known),
                len(df[df['scale'] == 'Unknown']),
                len(df_known[df_known['mode'] == 1]) if not df_known.empty else 0,
                len(df_known[df_known['mode'] == 0]) if not df_known.empty else 0,
                df_known['scale'].mode()[0] if not df_known.empty else 'N/A'
            ]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Get workbook and worksheets
        workbook = writer.book
        worksheet1 = writer.sheets['Playlist Analysis']
        worksheet2 = writer.sheets['Summary']
        
        # Add formatting
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })
        
        # Apply header formatting to both sheets
        for col_num, value in enumerate(df.columns.values):
            worksheet1.write(0, col_num, value, header_format)
        
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet2.write(0, col_num, value, header_format)
        
        # Adjust column widths
        worksheet1.set_column('A:A', 40)  # Track name
        worksheet1.set_column('B:B', 30)  # Artist
        worksheet1.set_column('C:C', 15)  # Scale
        
        worksheet2.set_column('A:A', 25)
        worksheet2.set_column('B:B', 20)
    
    return output.getvalue()

def export_to_pdf(df, playlist_name):
    """Export data to PDF"""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    
    # Title
    elements.append(Paragraph(f"SpotifyScaler Analysis: {playlist_name}", title_style))
    elements.append(Spacer(1, 0.5*inch))
    
    # Summary statistics
    df_known = df[df['scale'] != 'Unknown']
    major_count = len(df_known[df_known['mode'] == 1]) if not df_known.empty else 0
    minor_count = len(df_known[df_known['mode'] == 0]) if not df_known.empty else 0
    unknown_count = len(df[df['scale'] == 'Unknown'])
    
    summary_data = [
        ['Total Songs', str(len(df))],
        ['Songs with Scale Data', str(len(df_known))],
        ['Major Songs', str(major_count)],
        ['Minor Songs', str(minor_count)],
        ['Unknown Scale', str(unknown_count)],
        ['Most Common Scale', df_known['scale'].mode()[0] if not df_known.empty else 'N/A']
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Track list table
        # Track list table
    elements.append(Paragraph("Track List by Scale", styles['Heading2']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Sort by scale
    df_sorted = df.sort_values('scale')
    
    # Prepare data for table
    table_data = [['Track', 'Artist', 'Scale']]
    for _, row in df_sorted.iterrows():
        table_data.append([
            row['name'][:40] + '...' if len(row['name']) > 40 else row['name'],
            row['artist'][:30] + '...' if len(row['artist']) > 30 else row['artist'],
            row['scale']
        ])
    
    # Create table
    track_table = Table(table_data)
    track_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(track_table)
    
    # Build PDF
    doc.build(elements)
    return output.getvalue()

def main():
    st.set_page_config(page_title="SpotifyScaler", page_icon="🎵", layout="wide")
    
    st.title("🎵 SpotifyScaler")
    st.markdown("Analyze the musical scale distribution of any Spotify playlist")
    
    # Initialize Spotify client
    sp = init_spotify()
    if not sp:
        st.info("""
        ### How to set up Spotify credentials:
        
        1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
        2. Create a new app or use an existing one
        3. Copy your Client ID and Client Secret
        4. Add them to your Streamlit app's secrets
        
        **Note**: This app only analyzes public playlists and doesn't require user login.
        """)
        return
    
    # Sidebar for input
    with st.sidebar:
        st.header("Configuration")
        
        playlist_url = st.text_input("Enter Spotify Playlist URL:", 
                                   placeholder="https://open.spotify.com/playlist/...")
        
        classification_type = st.radio(
            "Classification Type:",
            ["Strict Classification", "Relative Classification"],
            help="Strict: Keep Major/Minor separate\nRelative: Group relative pairs (e.g., C Major ↔ A Minor)"
        )
        
        analyze_button = st.button("Analyze Playlist", type="primary")
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown("""
        SpotifyScaler analyzes the musical scales of songs in a Spotify playlist.
        
        **Features:**
        - Scale distribution visualization
        - Major vs Minor analysis
        - Export to Excel/PDF
        - Scale explorer
        
        **Note**: Some tracks may show as "Unknown" if Spotify doesn't have scale data for them.
        """)
    
    if analyze_button and playlist_url:
        playlist_id = extract_playlist_id(playlist_url)
        
        if not playlist_id:
            st.error("Invalid Spotify playlist URL. Please make sure you're using a valid playlist link.")
            return
        
        with st.spinner("Fetching playlist data..."):
            try:
                # Get playlist info
                playlist_info = sp.playlist(playlist_id)
                playlist_name = playlist_info['name']
                
                # Fetch tracks
                df = fetch_playlist_data(sp, playlist_id)
                
                if df.empty:
                    st.warning("No tracks found in the playlist")
                    return
                
                # Store in session state
                st.session_state['playlist_data'] = df
                st.session_state['playlist_name'] = playlist_name
                
            except Exception as e:
                st.error(f"Error fetching playlist: {str(e)}")
                return
    
    # Display results
    if 'playlist_data' in st.session_state:
        df = st.session_state['playlist_data']
        playlist_name = st.session_state['playlist_name']
        
        st.header(f"Analysis Results: {playlist_name}")
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Visualizations", "🎵 Track List", "🔍 Scale Explorer", "💾 Export"])
        
        with tab1:
            # Create charts
            charts = create_distribution_charts(df, classification_type)
            
            if charts[0] is not None:
                fig_bar, fig_pie, fig_ratio = charts
                
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(fig_bar, use_container_width=True)
                with col2:
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                st.plotly_chart(fig_ratio, use_container_width=True)
            
            # Summary statistics
            st.subheader("Summary Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            df_known = df[df['scale'] != 'Unknown']
            
            with col1:
                st.metric("Total Songs", len(df))
            with col2:
                st.metric("Songs with Scale Data", len(df_known))
            with col3:
                st.metric("Major Songs", len(df_known[df_known['mode'] == 1]) if not df_known.empty else 0)
            with col4:
                st.metric("Minor Songs", len(df_known[df_known['mode'] == 0]) if not df_known.empty else 0)
            
            # Additional insights
            if not df_known.empty:
                st.subheader("Additional Insights")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    most_common = df_known['scale'].mode()[0]
                    st.metric("Most Common Scale", most_common)
                
                with col2:
                    avg_tempo = df_known[df_known['tempo'] > 0]['tempo'].mean()
                    st.metric("Average Tempo", f"{avg_tempo:.1f} BPM" if not pd.isna(avg_tempo) else "N/A")
                
                with col3:
                    avg_energy = df_known[df_known['energy'] > 0]['energy'].mean()
                    st.metric("Average Energy", f"{avg_energy:.2f}" if not pd.isna(avg_energy) else "N/A")
        
        with tab2:
            # Display track list
            st.subheader("All Tracks")
            
            # Add search functionality
            search_term = st.text_input("Search tracks:", placeholder="Enter track or artist name...")
            
            # Apply grouping if relative classification
            if classification_type == "Relative Classification":
                df_display = df.copy()
                df_display['Scale Group'] = df_display['scale'].apply(get_relative_group)
                
                # Filter by search term
                if search_term:
                    mask = (df_display['name'].str.contains(search_term, case=False, na=False) | 
                           df_display['artist'].str.contains(search_term, case=False, na=False))
                    df_display = df_display[mask]
                
                # Show data
                if not df_display.empty:
                    st.dataframe(
                        df_display[['name', 'artist', 'scale', 'Scale Group']],
                        use_container_width=True,
                        height=600
                    )
                else:
                    st.info("No tracks found matching your search.")
            else:
                df_display = df.copy()
                
                # Filter by search term
                if search_term:
                    mask = (df_display['name'].str.contains(search_term, case=False, na=False) | 
                           df_display['artist'].str.contains(search_term, case=False, na=False))
                    df_display = df_display[mask]
                
                # Show data
                if not df_display.empty:
                    st.dataframe(
                        df_display[['name', 'artist', 'scale']],
                        use_container_width=True,
                        height=600
                    )
                else:
                    st.info("No tracks found matching your search.")
        
        with tab3:
            # Scale explorer
            st.subheader("Scale Explorer")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if classification_type == "Relative Classification":
                    # Get unique scale groups
                    df['scale_group'] = df['scale'].apply(get_relative_group)
                    scale_options = sorted(df['scale_group'].unique())
                    selected_scale = st.selectbox("Select a scale group:", scale_options)
                    
                    # Filter tracks
                    filtered_df = df[df['scale_group'] == selected_scale]
                else:
                    scale_options = sorted(df['scale'].unique())
                    selected_scale = st.selectbox("Select a scale:", scale_options)
                    
                    # Filter tracks
                    filtered_df = df[df['scale'] == selected_scale]
                
                st.metric("Songs in this scale", len(filtered_df))
                
                # Show average characteristics
                if selected_scale != "Unknown" and not filtered_df.empty:
                    st.markdown("**Average Characteristics:**")
                    
                    valid_tempo = filtered_df[filtered_df['tempo'] > 0]['tempo']
                    valid_energy = filtered_df[filtered_df['energy'] > 0]['energy']
                    valid_valence = filtered_df[filtered_df['valence'] > 0]['valence']
                    
                    if not valid_tempo.empty:
                        st.write(f"Tempo: {valid_tempo.mean():.1f} BPM")
                    if not valid_energy.empty:
                        st.write(f"Energy: {valid_energy.mean():.2f}")
                    if not valid_valence.empty:
                        st.write(f"Valence: {valid_valence.mean():.2f}")
            
            with col2:
                st.write(f"**Tracks in {selected_scale}:**")
                if not filtered_df.empty:
                    st.dataframe(
                        filtered_df[['name', 'artist']],
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No tracks found in this scale.")
        
        with tab4:
            # Export options
            st.subheader("Export Data")
            
            st.markdown("""
            Download your playlist analysis in your preferred format:
            - **Excel**: Includes summary statistics and full track list
            - **PDF**: Formatted report with summary data
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Excel export
                excel_data = export_to_excel(df)
                st.download_button(
                    label="📊 Download Excel Report",
                    data=excel_data,
                    file_name=f"spotify_scaler_{playlist_name.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col2:
                # PDF export
                pdf_data = export_to_pdf(df, playlist_name)
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_data,
                    file_name=f"spotify_scaler_{playlist_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Display export preview
            st.markdown("---")
            st.subheader("Export Preview")
            
            with st.expander("View Summary Statistics"):
                df_known = df[df['scale'] != 'Unknown']
                summary_stats = {
                    'Total Songs': len(df),
                    'Songs with Scale Data': len(df_known),
                    'Songs without Scale Data': len(df[df['scale'] == 'Unknown']),
                    'Major Songs': len(df_known[df_known['mode'] == 1]) if not df_known.empty else 0,
                    'Minor Songs': len(df_known[df_known['mode'] == 0]) if not df_known.empty else 0,
                    'Most Common Scale': df_known['scale'].mode()[0] if not df_known.empty else 'N/A',
                    'Success Rate': f"{(len(df_known) / len(df) * 100):.1f}%" if len(df) > 0 else "0%"
                }
                
                for key, value in summary_stats.items():
                    st.write(f"**{key}:** {value}")

if __name__ == "__main__":
    main()