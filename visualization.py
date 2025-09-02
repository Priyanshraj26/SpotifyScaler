import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from constants import CIRCLE_OF_FIFTHS_ORDER

def create_visualizations(df):
    """Create all analysis visualizations"""
    fig_keys = create_key_distribution_chart(df)
    fig_mode = create_mode_pie_chart(df)
    fig_tempo = create_tempo_histogram(df)
    fig_conf = create_confidence_box_plot(df)
    fig_circle = create_circle_of_fifths(df)
    
    return fig_keys, fig_mode, fig_tempo, fig_conf, fig_circle

def create_key_distribution_chart(df):
    """Create bar chart for key distribution"""
    key_counts = df['scale'].value_counts().reset_index()
    key_counts.columns = ['scale', 'count']
    
    fig = px.bar(
        key_counts, 
        x='scale', 
        y='count',
        title="Track Distribution by Key",
        labels={'scale': 'Key', 'count': 'Number of Tracks'},
        color='count',
        color_continuous_scale='viridis'
    )
    fig.update_layout(xaxis_tickangle=-45)
    
    return fig

def create_mode_pie_chart(df):
    """Create pie chart for major vs minor distribution"""
    mode_counts = df['mode'].value_counts().reset_index()
    mode_counts.columns = ['mode', 'count']
    
    fig = px.pie(
        mode_counts,
        names='mode',
        values='count',
        title="Major vs Minor Distribution",
        color_discrete_map={'major': '#FF6B6B', 'minor': '#4ECDC4'}
    )
    
    return fig

def create_tempo_histogram(df):
    """Create histogram for tempo distribution"""
    tempo_df = df[df['tempo'] > 0]
    
    if len(tempo_df) > 0:
        fig = px.histogram(
            tempo_df,
            x='tempo',
            nbins=20,
            title="Tempo Distribution",
            labels={'tempo': 'BPM', 'count': 'Number of Tracks'}
        )
    else:
        fig = go.Figure()
        fig.add_annotation(
            text="No tempo data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(title="Tempo Distribution")
    
    return fig

def create_confidence_box_plot(df):
    """Create box plot for confidence scores by mode"""
    fig = px.box(
        df,
        y='confidence',
        x='mode',
        title="Key Detection Confidence by Mode",
        labels={'confidence': 'Confidence Score', 'mode': 'Mode'}
    )
    
    return fig

def create_circle_of_fifths(df):
    """Create circle of fifths visualization"""
    circle_data = df.groupby('key').size().reset_index(name='count')
    
    # Create complete data with zeros for missing keys
    complete_circle_data = []
    for key in CIRCLE_OF_FIFTHS_ORDER:
        count = circle_data[circle_data['key'] == key]['count'].values
        complete_circle_data.append({
            'key': key,
            'count': count[0] if len(count) > 0 else 0
        })
    
    circle_df = pd.DataFrame(complete_circle_data)
    
    fig = go.Figure()
    
    if circle_df['count'].sum() > 0:
        fig.add_trace(go.Scatterpolar(
            r=circle_df['count'],
            theta=circle_df['key'],
            fill='toself',
            name='Track Count',
            line_color='rgb(106, 90, 205)',
            fillcolor='rgba(106, 90, 205, 0.3)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max(circle_df['count'].max() * 1.1, 1)]
                )),
            showlegend=False,
            title="Keys on Circle of Fifths"
        )
    else:
        fig.add_annotation(
            text="No key data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(title="Keys on Circle of Fifths")
    
    return fig

def create_key_transition_chart(transitions_df):
    """Create scatter plot for key transitions"""
    fig = px.scatter(
        transitions_df,
        x='position',
        y='distance',
        hover_data=['from', 'to'],
        title="Key Distance Between Consecutive Tracks",
        labels={'position': 'Track Position', 'distance': 'Semitone Distance'}
    )
    
    return fig