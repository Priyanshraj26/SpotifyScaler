import streamlit as st
import pandas as pd
from datetime import datetime

def display_disclaimer():
    """Display legal disclaimer"""
    with st.expander("⚠️ Important Legal Notice"):
        st.warning("""
        **Copyright Notice**: This tool is for educational and personal use only. 
        - Only analyze music you have rights to use
        - Downloaded files are automatically deleted after analysis
        - Do not distribute downloaded content
        - Respect copyright laws in your jurisdiction
        """)

def display_sidebar_settings():
    """Display sidebar settings and return selected options"""
    with st.sidebar:
        st.header("Input Options")
        
        input_mode = st.radio(
            "Select input source:",
            ["Upload Audio File", "Spotify Track", "Spotify Playlist"]
        )
        
        st.markdown("---")
        
        # Settings
        st.subheader("Settings")
        use_cache = st.checkbox("Use cache for repeated files", value=True)
        auto_cleanup = st.checkbox("Auto-cleanup after analysis", value=True)
        
        return input_mode, use_cache, auto_cleanup

def display_overview_tab(df):
    """Display overview statistics"""
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tracks", len(df))
    
    with col2:
        avg_tempo = df[df['tempo'] > 0]['tempo'].mean()
        st.metric("Avg Tempo", f"{avg_tempo:.1f} BPM" if not pd.isna(avg_tempo) else "N/A")
    
    with col3:
        avg_confidence = df['confidence'].mean()
        st.metric("Avg Confidence", f"{avg_confidence:.2%}")
    
    with col4:
        most_common = df['scale'].mode()[0] if not df.empty else "N/A"
        st.metric("Most Common Key", most_common)
    
    # Key distribution summary
    st.subheader("Key Distribution")
    key_summary = df['scale'].value_counts().reset_index()
    key_summary.columns = ['Key', 'Count']
    key_summary['Percentage'] = (key_summary['Count'] / len(df) * 100).round(1)
    
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(key_summary, use_container_width=True, hide_index=True)
    
    with col2:
        # Mode distribution
        mode_dist = df['mode'].value_counts()
        st.write("**Mode Distribution:**")
        for mode, count in mode_dist.items():
            percentage = count / len(df) * 100
            st.write(f"- {mode.capitalize()}: {count} tracks ({percentage:.1f}%)")

def display_detailed_results_tab(df):
    """Display detailed results with filters"""
    st.subheader("Track Analysis Details")
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    with col1:
        key_filter = st.multiselect("Filter by key:", options=df['key'].unique(), default=df['key'].unique())
    with col2:
        mode_filter = st.multiselect("Filter by mode:", options=df['mode'].unique(), default=df['mode'].unique())
    with col3:
        confidence_threshold = st.slider("Min confidence:", 0.0, 1.0, 0.0, 0.05)
    
    # Apply filters
    filtered_df = df[
        (df['key'].isin(key_filter)) & 
        (df['mode'].isin(mode_filter)) & 
        (df['confidence'] >= confidence_threshold)
    ]
    
    # Display table
    display_columns = ['track', 'artist', 'scale', 'tempo', 'confidence', 'energy', 'brightness']
    st.dataframe(
        filtered_df[display_columns].round(3),
        use_container_width=True,
        hide_index=True
    )
    
    # Track details expander
    st.subheader("Individual Track Details")
    for idx, row in filtered_df.iterrows():
        with st.expander(f"{row['track']} - {row['artist']}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Key:** {row['key']}")
                st.write(f"**Mode:** {row['mode'].capitalize()}")
                st.write(f"**Scale:** {row['scale']}")
            with col2:
                st.write(f"**Tempo:** {row['tempo']:.1f} BPM")
                st.write(f"**Confidence:** {row['confidence']:.1%}")
                st.write(f"**Energy:** {row['energy']:.3f}")

def display_export_tab(df, csv_data, excel_data, json_data):
    """Display export options"""
    st.subheader("Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV export
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"key_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Excel export
        st.download_button(
            label="📊 Download as Excel",
            data=excel_data,
            file_name=f"key_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # JSON export
    st.subheader("Developer Export")
    st.download_button(
        label="🔧 Download as JSON",
        data=json_data,
        file_name=f"key_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )