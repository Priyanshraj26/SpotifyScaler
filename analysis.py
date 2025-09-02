import numpy as np
import librosa
import pandas as pd
import os
from cache_utils import get_file_hash, load_from_cache, save_to_cache
from constants import KRUMHANSL_MAJOR, KRUMHANSL_MINOR, KEY_NAMES


def relative_major_minor(key_index, mode):
    """Return relative key (major <-> minor)"""
    if mode == "minor":  
        # relative major is +3 semitones
        rel_index = (key_index + 3) % 12
        return f"{KEY_NAMES[rel_index]} major"
    elif mode == "major":
        # relative minor is -3 semitones (or +9)
        rel_index = (key_index - 3) % 12
        return f"{KEY_NAMES[rel_index]} minor"
    return ""


def detect_key_librosa(filepath, use_cache=True):
    """Detect key and scale using librosa with Krumhansl-Schmuckler algorithm"""
    try:
        # Check cache first
        file_hash = get_file_hash(filepath)
        if use_cache:
            cached = load_from_cache(file_hash)
            if cached:
                return cached
        
        # Load audio
        y, sr = librosa.load(filepath, sr=22050, mono=True, duration=120)  # Analyze first 2 minutes
        
        # Harmonic-percussive separation
        y_harmonic, _ = librosa.effects.hpss(y)
        
        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=512)
        chroma_mean = np.mean(chroma, axis=1)
        
        # Normalize
        chroma_norm = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-8)
        
        # Compute correlation with all keys
        maj_scores = []
        min_scores = []
        for i in range(12):
            maj_scores.append(np.dot(chroma_norm, np.roll(KRUMHANSL_MAJOR, i)))
            min_scores.append(np.dot(chroma_norm, np.roll(KRUMHANSL_MINOR, i)))
        
        maj_scores = np.array(maj_scores)
        min_scores = np.array(min_scores)
        
        # Find best match
        maj_best = maj_scores.argmax()
        min_best = min_scores.argmax()
        maj_val = maj_scores.max()
        min_val = min_scores.max()
        
        if maj_val >= min_val:
            key_index = maj_best
            mode = "major"
            confidence = float(maj_val / (maj_val + min_val + 1e-8))
        else:
            key_index = min_best
            mode = "minor"
            confidence = float(min_val / (maj_val + min_val + 1e-8))
        
        detected_key = KEY_NAMES[key_index]
        
        # Additional features
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        
        # Energy (RMS)
        rms = librosa.feature.rms(y=y)
        energy = float(np.mean(rms))
        
        # Spectral centroid (brightness)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = float(np.mean(cent))

        rel = relative_major_minor(key_index, mode)

        results = {
            "key": detected_key,
            "mode": mode,
            "confidence": round(confidence, 3),
            "tempo": round(float(tempo), 1),
            "energy": round(energy, 3),
            "brightness": round(brightness, 1),
            "scale": f"{detected_key}{'m' if mode=='minor' else ''}/{rel.split()[0]}" 
        }
        
        # Save to cache
        if use_cache:
            save_to_cache(file_hash, results)
        
        return results
        
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return {
            "key": "Unknown",
            "mode": "unknown",
            "confidence": 0.0,
            "tempo": 0.0,
            "energy": 0.0,
            "brightness": 0.0,
            "scale": "Unknown"
        }

def extract_metadata_from_filename(filepath):
    """Extract track and artist from spotDL filename format"""
    filename = os.path.basename(filepath)
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # spotDL format: "Artist - Track.mp3"
    if " - " in name:
        parts = name.split(" - ", 1)
        return {"artist": parts[0], "track": parts[1]}
    else:
        return {"artist": "Unknown", "track": name}

def analyze_files(files, progress_callback=None, use_cache=True):
    """Analyze multiple audio files"""
    results = []
    
    for i, filepath in enumerate(files):
        if progress_callback:
            progress_callback(i, len(files))
        
        # Extract metadata
        metadata = extract_metadata_from_filename(filepath)
        
        # Analyze audio
        analysis = detect_key_librosa(str(filepath), use_cache=use_cache)
        
        # Combine results
        result = {
            "file": os.path.basename(filepath),
            "artist": metadata["artist"],
            "track": metadata["track"],
            **analysis
        }
        results.append(result)
    
    return pd.DataFrame(results)

def calculate_key_transitions(df):
    """Calculate key transitions for playlist analysis"""
    from constants import KEY_NAMES
    
    key_to_num = {k: i for i, k in enumerate(KEY_NAMES)}
    df['key_num'] = df['key'].map(key_to_num)
    
    transitions = []
    for i in range(len(df) - 1):
        curr_key = df.iloc[i]['key']
        next_key = df.iloc[i + 1]['key']
        curr_num = key_to_num.get(curr_key, 0)
        next_num = key_to_num.get(next_key, 0)
        
        # Calculate semitone distance
        distance = min(abs(next_num - curr_num), 12 - abs(next_num - curr_num))
        transitions.append({
            'position': i + 1,
            'from': f"{curr_key} {df.iloc[i]['mode']}",
            'to': f"{next_key} {df.iloc[i + 1]['mode']}",
            'distance': distance
        })
    
    return pd.DataFrame(transitions)