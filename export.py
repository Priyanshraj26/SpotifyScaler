import pandas as pd
from datetime import datetime
from io import BytesIO
import json

def export_to_csv(df):
    """Export dataframe to CSV"""
    export_df = prepare_export_data(df)
    return export_df.to_csv(index=False)

def export_to_excel(df):
    """Export dataframe to Excel with formatting"""
    output = BytesIO()
    export_df = prepare_export_data(df)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Main results sheet
        export_df.to_excel(writer, sheet_name='Analysis Results', index=False)
        
        # Summary sheet
        summary_df = create_summary_dataframe(df)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Key distribution sheet
        key_dist = df['scale'].value_counts().reset_index()
        key_dist.columns = ['Key', 'Count']
        key_dist['Percentage'] = (key_dist['Count'] / len(df) * 100).round(1)
        key_dist.to_excel(writer, sheet_name='Key Distribution', index=False)
        
        # Format the Excel file
        format_excel_sheets(writer, export_df, summary_df, key_dist)
    
    return output.getvalue()

def export_to_json(df):
    """Export dataframe to JSON"""
    export_df = prepare_export_data(df)
    
    # Convert to JSON with proper formatting
    json_data = export_df.to_dict(orient='records')
    
    # Add metadata
    export_data = {
        "metadata": {
            "analysis_date": datetime.now().isoformat(),
            "total_tracks": len(df),
            "tool": "Spotify Key Analyzer",
            "version": "1.0.0"
        },
        "summary": create_summary_dict(df),
        "tracks": json_data
    }
    
    return json.dumps(export_data, indent=2)

def prepare_export_data(df):
    """Prepare dataframe for export"""
    export_df = df.copy()
    export_df['analysis_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return export_df

def create_summary_dataframe(df):
    """Create summary statistics dataframe"""
    tempo_data = df[df['tempo'] > 0]['tempo']
    
    summary_data = {
        'Metric': [
            'Total Tracks',
            'Average Tempo',
            'Average Confidence',
            'Most Common Key',
            'Major Tracks',
            'Minor Tracks',
            'Unknown Keys',
            'Avg Energy',
            'Avg Brightness'
        ],
        'Value': [
            len(df),
            f"{tempo_data.mean():.1f} BPM" if not tempo_data.empty else "N/A",
            f"{df['confidence'].mean():.1%}",
            df['scale'].mode()[0] if not df.empty else "N/A",
            len(df[df['mode'] == 'major']),
            len(df[df['mode'] == 'minor']),
            len(df[df['key'] == 'Unknown']),
            f"{df['energy'].mean():.3f}",
            f"{df['brightness'].mean():.1f}"
        ]
    }
    
    return pd.DataFrame(summary_data)

def create_summary_dict(df):
    """Create summary statistics dictionary"""
    tempo_data = df[df['tempo'] > 0]['tempo']
    
    return {
        'total_tracks': len(df),
        'average_tempo': float(tempo_data.mean()) if not tempo_data.empty else None,
        'average_confidence': float(df['confidence'].mean()),
        'most_common_key': df['scale'].mode()[0] if not df.empty else None,
        'major_tracks': int(len(df[df['mode'] == 'major'])),
        'minor_tracks': int(len(df[df['mode'] == 'minor'])),
        'unknown_keys': int(len(df[df['key'] == 'Unknown'])),
        'average_energy': float(df['energy'].mean()),
        'average_brightness': float(df['brightness'].mean())
    }

def format_excel_sheets(writer, export_df, summary_df, key_dist):
    """Apply formatting to Excel sheets"""
    workbook = writer.book
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4CAF50',
        'font_color': 'white',
        'border': 1
    })
    
    # Format each sheet
    sheets_data = [
        ('Analysis Results', export_df),
        ('Summary', summary_df),
        ('Key Distribution', key_dist)
    ]
    
    for sheet_name, df in sheets_data:
        worksheet = writer.sheets[sheet_name]
        
        # Apply header format
        for col_num, value in enumerate(df.columns):
            worksheet.write(0, col_num, value, header_format)
        
        # Auto-fit columns
        for i, col in enumerate(df.columns):
            column_width = max(len(str(col)), 15)
            worksheet.set_column(i, i, column_width)