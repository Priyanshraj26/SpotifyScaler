import numpy as np
import librosa
import pandas as pd
import os
from scipy.stats import pearsonr
from cache_utils import get_file_hash, load_from_cache, save_to_cache
from constants import KRUMHANSL_MAJOR, KRUMHANSL_MINOR, KEY_NAMES

# Additional key profiles for better accuracy
TEMPERLEY_MAJOR = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
TEMPERLEY_MINOR = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])

# Albrecht & Shanahan profiles (2013) - more accurate for pop/rock
ALBRECHT_MAJOR = np.array([6.44, 2.00, 3.48, 2.19, 4.54, 3.53, 2.39, 5.11, 2.39, 3.66, 2.29, 3.29])
ALBRECHT_MINOR = np.array([6.26, 2.68, 3.48, 5.83, 2.88, 3.69, 2.46, 5.12, 4.04, 2.69, 3.34, 3.24])

def get_enhanced_chroma(y, sr):
    """Extract multiple chroma representations for better accuracy"""
    # Harmonic-percussive separation
    y_harmonic, _ = librosa.effects.hpss(y, margin=8)
    
    # Multiple chroma types
    chroma_cqt = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=512, bins_per_octave=36)
    chroma_stft = librosa.feature.chroma_stft(y=y_harmonic, sr=sr, hop_length=512, n_fft=4096)
    chroma_cens = librosa.feature.chroma_cens(y=y_harmonic, sr=sr, hop_length=512)
    
    # Weight different chroma types
    chroma_combined = 0.5 * chroma_cqt + 0.3 * chroma_stft + 0.2 * chroma_cens
    
    return chroma_combined

def correlate_with_profiles(chroma_vector, profile_major, profile_minor):
    """Correlate chroma with key profiles using Pearson correlation"""
    major_corrs = []
    minor_corrs = []
    
    for shift in range(12):
        major_corr, _ = pearsonr(chroma_vector, np.roll(profile_major, shift))
        minor_corr, _ = pearsonr(chroma_vector, np.roll(profile_minor, shift))
        major_corrs.append(major_corr)
        minor_corrs.append(minor_corr)
    
    return np.array(major_corrs), np.array(minor_corrs)

def detect_key_enhanced(y, sr):
    """Enhanced key detection using multiple methods"""
    # Get enhanced chroma
    chroma = get_enhanced_chroma(y, sr)
    
    # Use median instead of mean for robustness
    chroma_median = np.median(chroma, axis=1)
    
    # Normalize
    chroma_norm = chroma_median / (np.sum(chroma_median) + 1e-8)
    
    # Try multiple key profiles
    profiles = [
        (KRUMHANSL_MAJOR, KRUMHANSL_MINOR, 0.3),  # weight 30%
        (TEMPERLEY_MAJOR, TEMPERLEY_MINOR, 0.3),  # weight 30%
        (ALBRECHT_MAJOR, ALBRECHT_MINOR, 0.4),    # weight 40% (best for modern music)
    ]
    
    weighted_major_scores = np.zeros(12)
    weighted_minor_scores = np.zeros(12)
    
    for major_prof, minor_prof, weight in profiles:
        maj_corrs, min_corrs = correlate_with_profiles(chroma_norm, major_prof, minor_prof)
        weighted_major_scores += weight * maj_corrs
        weighted_minor_scores += weight * min_corrs
    
    # Find best matches
    major_idx = np.argmax(weighted_major_scores)
    minor_idx = np.argmax(weighted_minor_scores)
    major_score = weighted_major_scores[major_idx]
    minor_score = weighted_minor_scores[minor_idx]
    
    # Determine key and confidence
    if major_score > minor_score:
        key_idx = major_idx
        mode = "major"
        confidence = major_score / (major_score + minor_score + 1e-8)
        # Penalize if the score difference is small
        if abs(major_score - minor_score) < 0.05:
            confidence *= 0.8
    else:
        key_idx = minor_idx
        mode = "minor"
        confidence = minor_score / (major_score + minor_score + 1e-8)
        # Penalize if the score difference is small
        if abs(major_score - minor_score) < 0.05:
            confidence *= 0.8
    
    return key_idx, mode, confidence

def segment_based_detection(y, sr, segment_duration=10):
    """Detect key using segment-based voting"""
    segment_samples = int(segment_duration * sr)
    n_segments = max(1, len(y) // segment_samples)
    
    key_votes = []
    mode_votes = []
    confidences = []
    
    for i in range(n_segments):
        start = i * segment_samples
        end = min((i + 1) * segment_samples, len(y))
        segment = y[start:end]
        
        if len(segment) > sr:  # At least 1 second
            key_idx, mode, conf = detect_key_enhanced(segment, sr)
            key_votes.append(key_idx)
            mode_votes.append(mode)
            confidences.append(conf)
    
    if not key_votes:
        return 0, "major", 0.0
    
    # Weighted voting based on confidence
    key_weights = np.zeros(12)
    mode_weights = {"major": 0, "minor": 0}
    
    for key, mode, conf in zip(key_votes, mode_votes, confidences):
        key_weights[key] += conf
        mode_weights[mode] += conf
    
    final_key = np.argmax(key_weights)
    final_mode = "major" if mode_weights["major"] > mode_weights["minor"] else "minor"
    final_confidence = np.mean(confidences)
    
    return final_key, final_mode, final_confidence

def relative_major_minor(key_index, mode):
    """Return relative major/minor key name"""
    if mode == "minor":
        rel_index = (key_index + 3) % 12
        return f"{KEY_NAMES[rel_index]} major"
    elif mode == "major":
        rel_index = (key_index - 3) % 12
        return f"{KEY_NAMES[rel_index]} minor"
    return "Unknown"

def detect_key_librosa(filepath, use_cache=True):
    """Enhanced key detection with multiple algorithms and alternative keys"""
    try:
        # Check cache first
        file_hash = get_file_hash(filepath)
        if use_cache:
            cached = load_from_cache(file_hash)
            if cached:
                return cached
        
        # Load audio (analyze middle portion for better results)
        y, sr = librosa.load(filepath, sr=22050, mono=True)
        
        # Skip intro/outro (often have ambiguous harmony)
        if len(y) > 30 * sr:  # If longer than 30 seconds
            start = int(10 * sr)  # Skip first 10 seconds
            end = min(len(y) - int(10 * sr), int(120 * sr))  # Skip last 10 seconds, max 2 minutes
            y = y[start:end]
        
        # Method 1: Enhanced single detection
        key_idx1, mode1, conf1 = detect_key_enhanced(y, sr)
        
        # Method 2: Segment-based voting
        key_idx2, mode2, conf2 = segment_based_detection(y, sr)
        
        # Store the weighted scores for alternative keys
        # Get enhanced chroma for final scoring
        chroma = get_enhanced_chroma(y, sr)
        chroma_median = np.median(chroma, axis=1)
        chroma_norm = chroma_median / (np.sum(chroma_median) + 1e-8)
        
        # Calculate scores for all keys using all profiles
        profiles = [
            (KRUMHANSL_MAJOR, KRUMHANSL_MINOR, 0.3),
            (TEMPERLEY_MAJOR, TEMPERLEY_MINOR, 0.3),
            (ALBRECHT_MAJOR, ALBRECHT_MINOR, 0.4),
        ]
        
        weighted_major_scores = np.zeros(12)
        weighted_minor_scores = np.zeros(12)
        
        for major_prof, minor_prof, weight in profiles:
            maj_corrs, min_corrs = correlate_with_profiles(chroma_norm, major_prof, minor_prof)
            weighted_major_scores += weight * maj_corrs
            weighted_minor_scores += weight * min_corrs
        
        # Combine results from both methods with confidence weighting
        if conf1 > conf2 * 1.2:  # Strong preference for method 1
            key_index, mode, confidence = key_idx1, mode1, conf1
        elif conf2 > conf1 * 1.2:  # Strong preference for method 2
            key_index, mode, confidence = key_idx2, mode2, conf2
        else:  # Similar confidence, check if they agree
            if key_idx1 == key_idx2 and mode1 == mode2:
                key_index, mode = key_idx1, mode1
                confidence = (conf1 + conf2) / 2 * 1.1  # Boost confidence if methods agree
            else:
                # Disagreement - use the one with higher confidence
                if conf1 >= conf2:
                    key_index, mode, confidence = key_idx1, mode1, conf1 * 0.9
                else:
                    key_index, mode, confidence = key_idx2, mode2, conf2 * 0.9
        
        # Get alternative keys
        all_scores = []
        for i in range(12):
            all_scores.append((i, "major", weighted_major_scores[i]))
            all_scores.append((i, "minor", weighted_minor_scores[i]))
        
        # Sort by score descending
        all_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Find the main key in the sorted list to normalize scores
        main_score = 0
        for idx, (k_idx, m, score) in enumerate(all_scores):
            if k_idx == key_index and m == mode:
                main_score = score
                break
        
        # Get top alternatives (excluding the chosen key)
        alternative_keys = []
        alternatives_found = 0
        
        for key_idx_alt, mode_alt, score_alt in all_scores:
            # Skip if it's the main key
            if key_idx_alt == key_index and mode_alt == mode:
                continue
            
            key_name_alt = KEY_NAMES[key_idx_alt]
            scale_alt = f"{key_name_alt}{'m' if mode_alt=='minor' else ''}"
            
            # Calculate relative confidence
            conf_alt = score_alt / (main_score + 1e-8)
            
            alternative_keys.append((scale_alt, round(conf_alt, 3)))
            alternatives_found += 1
            
            if alternatives_found >= 3:  # Get top 3 alternatives
                break
        
        # Get the detected key name and relative
        detected_key = KEY_NAMES[key_index]
        rel = relative_major_minor(key_index, mode)
        
        # Additional features
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        
        # Adjust confidence based on signal characteristics
        energy = float(np.mean(rms))
        if energy < 0.01:  # Very low energy might indicate ambient/atonal music
            confidence *= 0.7
        
        results = {
            "key": detected_key,
            "mode": mode,
            "relative_scale": rel,
            "confidence": round(float(confidence), 3),
            "tempo": round(float(tempo), 1),
            "energy": round(energy, 3),
            "brightness": round(float(np.mean(cent)), 1),
            "scale": f"{detected_key}{'m' if mode=='minor' else ''}/{rel.split()[0]}",
            "alternative_keys": alternative_keys
        }
        
        if use_cache:
            save_to_cache(file_hash, results)
        
        return results
        
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return {
            "key": "Unknown",
            "mode": "unknown",
            "relative_scale": "Unknown",
            "confidence": 0.0,
            "tempo": 0.0,
            "energy": 0.0,
            "brightness": 0.0,
            "scale": "Unknown",
            "alternative_keys": []
        }

# Keep other functions unchanged
def extract_metadata_from_filename(filepath):
    """Extract track and artist from spotDL filename format"""
    filename = os.path.basename(filepath)
    name = os.path.splitext(filename)[0]
    
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
        
        metadata = extract_metadata_from_filename(filepath)
        analysis = detect_key_librosa(str(filepath), use_cache=use_cache)
        
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
    key_to_num = {k: i for i, k in enumerate(KEY_NAMES)}
    df['key_num'] = df['key'].map(key_to_num)
    
    transitions = []
    for i in range(len(df) - 1):
        curr_key = df.iloc[i]['key']
        next_key = df.iloc[i + 1]['key']
        curr_num = key_to_num.get(curr_key, 0)
        next_num = key_to_num.get(next_key, 0)
        
        distance = min(abs(next_num - curr_num), 12 - abs(next_num - curr_num))
        transitions.append({
            'position': i + 1,
            'from': f"{curr_key} {df.iloc[i]['mode']}",
            'to': f"{next_key} {df.iloc[i + 1]['mode']}",
            'distance': distance
        })
    
    return pd.DataFrame(transitions)