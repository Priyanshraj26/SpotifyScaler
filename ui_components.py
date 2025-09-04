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
        
        # Advanced settings
        with st.expander("Advanced Settings"):
            confidence_threshold = st.slider(
                "Minimum confidence for key detection",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05,
                help="Songs below this confidence will show a warning"
            )
            show_alternatives = st.checkbox(
                "Show alternative key suggestions",
                value=True,
                help="Display top 3 possible keys for each track"
            )
        
        return input_mode, use_cache, auto_cleanup, confidence_threshold, show_alternatives

def display_overview_tab(df):
    """Display overview statistics with confidence metrics"""
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tracks", len(df))
    
    with col2:
        avg_tempo = df[df['tempo'] > 0]['tempo'].mean()
        st.metric("Avg Tempo", f"{avg_tempo:.1f} BPM" if not pd.isna(avg_tempo) else "N/A")
    
    with col3:
        avg_confidence = df['confidence'].mean()
        color = "🟢" if avg_confidence > 0.7 else "🟡" if avg_confidence > 0.5 else "🔴"
        st.metric(f"{color} Avg Confidence", f"{avg_confidence:.2%}")
    
    with col4:
        most_common = df['scale'].mode()[0] if not df.empty else "N/A"
        st.metric("Most Common Key", most_common)
    
    # Confidence distribution
    st.subheader("Detection Confidence Overview")
    col1, col2, col3 = st.columns(3)
    
    high_conf = len(df[df['confidence'] >= 0.7])
    med_conf = len(df[(df['confidence'] >= 0.5) & (df['confidence'] < 0.7)])
    low_conf = len(df[df['confidence'] < 0.5])
    
    with col1:
        st.metric("🟢 High Confidence", f"{high_conf} ({high_conf/len(df)*100:.1f}%)")
    with col2:
        st.metric("🟡 Medium Confidence", f"{med_conf} ({med_conf/len(df)*100:.1f}%)")
    with col3:
        st.metric("🔴 Low Confidence", f"{low_conf} ({low_conf/len(df)*100:.1f}%)")
    
    # Key distribution summary
    st.subheader("Key Distribution")
    key_summary = df['scale'].value_counts().reset_index()
    key_summary.columns = ['Key', 'Count']
    key_summary['Percentage'] = (key_summary['Count'] / len(df) * 100).round(1)
    
    # Add average confidence per key
    key_confidence = df.groupby('scale')['confidence'].mean().round(3)
    key_summary['Avg Confidence'] = key_summary['Key'].map(key_confidence)
    
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(key_summary, use_container_width=True, hide_index=True)
    
    with col2:
        # Mode distribution
        mode_dist = df['mode'].value_counts()
        st.write("**Mode Distribution:**")
        for mode, count in mode_dist.items():
            percentage = count / len(df) * 100
            avg_conf = df[df['mode'] == mode]['confidence'].mean()
            st.write(f"- {mode.capitalize()}: {count} tracks ({percentage:.1f}%) - Avg confidence: {avg_conf:.2%}")

def display_detailed_results_tab(df, confidence_threshold=0.5, show_alternatives=True):
    """Display detailed results with confidence warnings and alternatives"""
    st.subheader("Track Analysis Details")
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    with col1:
        key_filter = st.multiselect("Filter by key:", options=df['key'].unique(), default=df['key'].unique())
    with col2:
        mode_filter = st.multiselect("Filter by mode:", options=df['mode'].unique(), default=df['mode'].unique())
    with col3:
        confidence_filter = st.slider("Min confidence:", 0.0, 1.0, 0.0, 0.05)
    
    # Apply filters
    filtered_df = df[
        (df['key'].isin(key_filter)) & 
        (df['mode'].isin(mode_filter)) & 
        (df['confidence'] >= confidence_filter)
    ]
    
    # Display warning for low confidence tracks
    low_conf_tracks = filtered_df[filtered_df['confidence'] < confidence_threshold]
    if len(low_conf_tracks) > 0:
        st.warning(f"⚠️ {len(low_conf_tracks)} tracks have low confidence (< {confidence_threshold:.0%}) in key detection")
    
    # Display table with confidence indicators
    display_df = filtered_df.copy()
    display_df['confidence_indicator'] = display_df['confidence'].apply(
        lambda x: '🟢' if x >= 0.7 else '🟡' if x >= 0.5 else '🔴'
    )
    
    display_columns = [
        'confidence_indicator',
        'track', 
        'artist', 
        'scale',
        'relative_scale',
        'tempo', 
        'confidence', 
        'energy', 
        'brightness'
    ]
    
    st.dataframe(
        display_df[display_columns].round(3),
        use_container_width=True,
        hide_index=True,
        column_config={
            'confidence_indicator': st.column_config.TextColumn('', width='small'),
            'confidence': st.column_config.NumberColumn('Confidence', format='%.1%'),
            'tempo': st.column_config.NumberColumn('Tempo', format='%.1f BPM'),
        }
    )
    
    # Track details expander with enhanced information
    st.subheader("Individual Track Details")
    for idx, row in filtered_df.iterrows():
        # Add confidence indicator to expander title
        conf_icon = '🟢' if row['confidence'] >= 0.7 else '🟡' if row['confidence'] >= 0.5 else '🔴'
        
        with st.expander(f"{conf_icon} {row['track']} - {row['artist']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Key:** {row['key']}")
                st.write(f"**Mode:** {row['mode'].capitalize()}")
                st.write(f"**Scale (Combined):** {row['scale']}")
                st.write(f"**Relative Scale:** {row['relative_scale']}")
                
                # Confidence with color coding
                conf_color = "green" if row['confidence'] >= 0.7 else "orange" if row['confidence'] >= 0.5 else "red"
                st.markdown(f"**Confidence:** <span style='color:{conf_color}'>{row['confidence']:.1%}</span>", 
                          unsafe_allow_html=True)
                
                # Warning for low confidence
                if row['confidence'] < confidence_threshold:
                    st.warning(f"⚠️ Low confidence - key detection may be inaccurate")
                
            with col2:
                st.write(f"**Tempo:** {row['tempo']:.1f} BPM")
                st.write(f"**Energy:** {row['energy']:.3f}")
                st.write(f"**Brightness:** {row['brightness']:.1f}")
                
                # Show alternative keys if available and enabled
                if show_alternatives and 'alternative_keys' in row and row['alternative_keys']:
                    st.write("**Alternative Keys:**")
                    for alt_key, alt_conf in row['alternative_keys'][:3]:  # Show top 3
                        st.write(f"  • {alt_key}: {alt_conf:.1%}")

def display_export_tab(df, csv_data, excel_data, json_data):
    """Display export options with confidence summary"""
    st.subheader("Export Options")
    
    # Add export summary
    with st.expander("Export Summary"):
        st.write(f"**Total tracks:** {len(df)}")
        st.write(f"**Average confidence:** {df['confidence'].mean():.1%}")
        st.write(f"**Tracks with high confidence (≥70%):** {len(df[df['confidence'] >= 0.7])}")
        st.write(f"**Tracks with low confidence (<50%):** {len(df[df['confidence'] < 0.5])}")
    
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