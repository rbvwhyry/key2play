import json
import os
import mido

from lib.log_setup import logger

DIR_SONGS_DEFAULT = "Songs_Default/"
DIR_SONGS_USER = "Songs_User_Upload/"
DIR_CACHE = "cache/"

def resolve_song_path(filename):
    user_path = os.path.join(DIR_SONGS_USER, filename)
    if os.path.exists(user_path):
        return user_path
    default_path = os.path.join(DIR_SONGS_DEFAULT, filename)
    if os.path.exists(default_path):
        return default_path
    return None

def get_note_name(midi_note):
    """Converts a MIDI note number (0-127) to a human-readable name like C4 or A#2."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    name = names[midi_note % 12]
    return f"{name}{octave}"

def has_playable_notes(file_path):
    """Returns True if the MIDI file contains at least one note_on with velocity > 0."""
    try:
        mid = mido.MidiFile(file_path, clip=True)

        for track in mid.tracks:
            for msg in track:
                if msg.type == "note_on" and msg.velocity > 0:
                    return True

        return False
    except Exception:
        return False

def get_tempo(mid):
    """Extracts the first tempo marker from a MIDI file. Returns 500000 (120 BPM) if none found."""
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return msg.tempo
    return 500000

def get_time_signature(mid):
    """Extracts the first time signature from a MIDI file. Returns '4/4' if none found."""
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'time_signature':
                return f"{msg.numerator}/{msg.denominator}"
    return "4/4"

def analyze_midi(filepath):
    """Parses a MIDI file and returns a dict of metadata.
    Single pass through merged tracks extracts everything we need."""
    try:
        mid = mido.MidiFile(filepath, clip=True)

        tempo = get_tempo(mid)
        bpm = round(mido.tempo2bpm(tempo))
        time_sig = get_time_signature(mid)
        ticks_per_beat = mid.ticks_per_beat
        track_count = len(mid.tracks)

        #merge all tracks for a single pass
        merged = mido.merge_tracks(mid.tracks)

        total_notes = 0
        active_notes = set()  #currently held notes at any point in time
        max_polyphony = 0  #highest number of simultaneous notes
        lowest_note = 127
        highest_note = 0
        unique_pitches = set()
        time_elapsed = 0.0

        for msg in merged:
            time_elapsed += mido.tick2second(msg.time, ticks_per_beat, tempo)

            if msg.type == 'note_on' and msg.velocity > 0:
                total_notes += 1
                active_notes.add(msg.note)
                unique_pitches.add(msg.note)

                if len(active_notes) > max_polyphony:
                    max_polyphony = len(active_notes)

                if msg.note < lowest_note:
                    lowest_note = msg.note

                if msg.note > highest_note:
                    highest_note = msg.note

            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                active_notes.discard(msg.note)

        #duration from mido's built-in calculation (accounts for tempo changes)
        duration = mid.length

        #notes per second — how busy the song is
        notes_per_second = round(total_notes / duration, 1) if duration > 0 else 0

        #note range as human-readable string
        if lowest_note <= highest_note:
            note_range = f"{get_note_name(lowest_note)}→{get_note_name(highest_note)}"
            range_semitones = highest_note - lowest_note
        else:
            note_range = "—"
            range_semitones = 0

        #difficulty score 1-5
        difficulty = calculate_difficulty(max_polyphony, notes_per_second, range_semitones)

        #format duration as "Xm Ys"
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        if minutes > 0 and seconds > 0:
            duration_str = f"{minutes}m {seconds}s"
        elif minutes > 0:
            duration_str = f"{minutes}m"
        else:
            duration_str = f"{seconds}s"

        #file size formatted for display
        file_size = os.path.getsize(filepath)
        if file_size >= 1048576:
            file_size_str = f"{round(file_size / 1048576, 1)} mb"
        else:
            file_size_str = f"{round(file_size / 1024)} kb"

        #difficulty as a plain word
        difficulty_words = ["", "beginner", "easy", "moderate", "hard", "expert"]
        difficulty_word = difficulty_words[difficulty]

        return {
            "file_size": file_size,
            "file_size_str": file_size_str,
            "duration": round(duration, 1),
            "duration_str": duration_str,
            "bpm": bpm,
            "bpm_str": f"{bpm} bpm",
            "time_signature": time_sig,
            "time_signature_str": f"{time_sig} time",
            "track_count": track_count,
            "total_notes": total_notes,
            "unique_pitches": len(unique_pitches),
            "max_polyphony": max_polyphony,
            "notes_per_second": notes_per_second,
            "note_range": note_range,
            "difficulty": difficulty,
            "difficulty_stars": "★" * difficulty + "☆" * (5 - difficulty),
            "difficulty_word": difficulty_word
        }

    except Exception as e:
        logger.warning(f"Failed to analyze {filepath}: {e}")
        return None

def calculate_difficulty(polyphony, notes_per_second, range_semitones):
    """Rough 1-5 difficulty score. Each of three factors scores 1-5,
    then they're averaged and rounded."""
    score = 0

    #polyphony: how many keys pressed simultaneously
    if polyphony >= 6:
        score += 5
    elif polyphony >= 4:
        score += 4
    elif polyphony >= 3:
        score += 3
    elif polyphony >= 2:
        score += 2
    else:
        score += 1

    #density: notes per second
    if notes_per_second >= 8:
        score += 5
    elif notes_per_second >= 4:
        score += 4
    elif notes_per_second >= 2:
        score += 3
    elif notes_per_second >= 1:
        score += 2
    else:
        score += 1

    #range: distance between lowest and highest note in semitones
    if range_semitones >= 48:
        score += 5
    elif range_semitones >= 36:
        score += 4
    elif range_semitones >= 24:
        score += 3
    elif range_semitones >= 12:
        score += 2
    else:
        score += 1

    return max(1, min(5, round(score / 3)))

def get_cache_path(filename):
    """Returns the path to the cached analysis JSON for a given song filename."""
    os.makedirs(DIR_CACHE, exist_ok=True)
    return os.path.join(DIR_CACHE, filename + ".info.json")

def get_song_info(filename):
    """Returns cached analysis for a song. If no cache exists, analyzes and caches it."""
    cache_path = get_cache_path(filename)

    #check cache first
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception:
            pass  #cache corrupt — re-analyze

    #no cache — analyze
    filepath = resolve_song_path(filename)
    if not filepath:
        return None

    info = analyze_midi(filepath)
    if not info:
        return None

    #save to cache
    try:
        with open(cache_path, "w") as f:
            json.dump(info, f)
    except Exception as e:
        logger.warning(f"Failed to cache song info for {filename}: {e}")

    return info

def get_all_songs_info():
    """Analyzes all songs in both folders and returns a dict keyed by filename."""
    result = {}

    for d in [DIR_SONGS_DEFAULT, DIR_SONGS_USER]:
        if not os.path.isdir(d):
            continue
        for filename in os.listdir(d):
            if not filename.lower().endswith((".mid", ".midi")):
                continue
            if filename in result:
                continue  #user folder version already processed
            info = get_song_info(filename)
            if info:
                result[filename] = info

    return result
