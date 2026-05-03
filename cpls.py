#!/usr/bin/python3

from shutil import copyfile
from pathlib import Path
from collections import defaultdict
from shlex import quote
import subprocess
import argparse
import os
import sys


parser = argparse.ArgumentParser(prog='cp_playlist', description='Copy music files from playlist to given directory.')
parser.add_argument('playlist_filename', help='file name of m3u playlist')
parser.add_argument('dst_dir', help='destination directory')
parser.add_argument('-r', '--replace', action='store_true', help='whether to replace destination files if they already exist')
parser.add_argument("-p", "--profile", default="default", help="Device profile name from the 'profiles/' directory (default: 'default')")
parser.add_argument('-d', '--dry', action='store_true', help='dry run, without copying or deleting files')
args = parser.parse_args()
real_run = not args.dry

# --- Load Profile Logic ---
supported_set = set()
mapping_dict = {}
    
# Locate the profile file in 'profiles/' directory relative to the script
script_dir = os.path.dirname(os.path.abspath(__file__))
profile_path = os.path.join(script_dir, 'profiles', args.profile)

if not os.path.exists(profile_path):
    print(f"Error: Profile '{args.profile}' not found at {profile_path}")
    if args.profile == "default":
        print("\nPlease create it by symlinking or copying an existing profile, e.g.:")
        if os.name == 'nt':  # Windows
            print(r"  copy profiles\wiim profiles\default")
        else:                # Linux/macOS (ln is preferred)
            print("  (cd profiles && ln -s wiim default)")
            print("or")
            print("  cp profiles/wiim profiles/default")
    sys.exit(1)

supported_formats = set()
change_extension = {}

# Load profile rules: first word is target, others map to it
try:
    with open(profile_path, 'r') as f:    # maybe encoding='latin-1'?
        for line in f:
            line = line.strip().lower()
            if line.startswith('#'): continue

            line = line.split()
            if not line: continue
            
            target_ext = line[0]
            supported_formats.add(target_ext)
            
            for source_ext in line[1:]:
                change_extension[source_ext] = target_ext
                supported_formats.add(source_ext)
except IOError as e:
    print(f"Error reading profile '{args.profile}': {e}")
    sys.exit(1)

# Check if the destination directory exists
if not os.path.isdir(args.dst_dir):
    print(f"Error: Destination directory '{args.dst_dir}' does not exist.")
    print("Please make sure your USB drive is mounted or the path is correct.")
    sys.exit(1)

playlist_filename = Path(args.playlist_filename)
dst_dir = Path(args.dst_dir)

def dst_file(src_file: Path) -> Path:
    src_file = src_file.with_suffix(src_file.suffix.lower())
    src_ext = src_file.suffix[1:]
    if src_ext in supported_formats:
        src_file = src_file.with_suffix('.' + change_extension.get(src_ext, src_ext))
    else:
        src_file = src_file.with_suffix('.mp3')
    return Path(src_file.name)

total_files = 0
dsts = defaultdict(list)    # maps destination file name to source file name(s)
with open(playlist_filename) as f:
    for src_file in f:
        if src_file.startswith("#"): continue
        src_file = playlist_filename.parent / Path(src_file.strip())
        dsts[dst_file(src_file)].append(src_file)
        total_files += 1

copied = set()
skipped = 0
converted = 0
while dsts:
    dst_file_candidate, src_files = dsts.popitem()
    number = 1
    for src_file in src_files:
        dst_file = dst_file_candidate
        while dst_file in dsts or dst_file.name in copied:
            dst_file = dst_file.with_stem(dst_file_candidate.stem + str(number))
            number += 1
        copied.add(dst_file.name)
        print(f"[{len(copied)}/{total_files}] {src_file.name}",
            f" -> {dst_file.name}" if src_file.name != dst_file.name else '', sep='')
        dst_file = dst_dir / dst_file
        if not args.replace and dst_file.exists():
            print("  destination file exists, skipped (run with -r flag to overwrite)")
            skipped += 1
            continue
        if src_file.suffix[1:].lower() in supported_formats: # copy:
            if real_run: copyfile(src_file, dst_file)
        else:   # convert to mp3:
            if real_run: subprocess.run(["ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-i", str(src_file), "-codec:a", "libmp3lame", "-qscale:a", "2",
                "-map_metadata", "0:s:a:0", "-id3v2_version", "3", "-write_id3v1", "1",
                str(dst_file)])
            converted += 1
print(f'{len(copied)} processed, {converted} transcoded, {skipped} skipped')

# Suggests deleting extra files from destination:
to_del = [f.name for f in dst_dir.iterdir() if f.is_file() and f.name not in copied]
if to_del:
    print(f'The destination directory contains {len(to_del)} extra files:')
    for to_del_file in to_del:
        print(quote(to_del_file), end=' ')
