#!/usr/bin/env python3

from shutil import copyfile
from pathlib import Path
from collections import defaultdict
from shlex import quote
import subprocess
import argparse
import os
import sys

parser = argparse.ArgumentParser(prog='cpls', description='Copy music files from playlist to given directory.')
parser.add_argument('playlist_filename', help='file name of m3u playlist')
parser.add_argument('dst_dir', help='destination directory')
parser.add_argument('-r', '--replace', '--overwrite', action='store_true', help='whether to replace destination files if they already exist')
parser.add_argument('-p', '--profile', '--dev', '--device', nargs='?', default=None, const='default', help="If the flag is not given, the files are copied without transcoding. Otherwise, transcoding is performed according to the device profile, with the name specified or 'default'. Profile files are read from the 'profiles/' directory.")
parser.add_argument('--dry', action='store_true', help='dry run, without copying or deleting files')
parser.add_argument('-l', '--lists', '--play_lists', help='Save playlist(s) in destination. If one list is not enough, the number of lists can be given. Extra lists are shuffled.', nargs='?', const=1, default=0, type=int)
del_args = parser.add_mutually_exclusive_group()
del_args.add_argument('--del', '--delete', '--autodel', '--rm', dest='autodel', action='store_true', help='delete extra files in destination directory')
del_args.add_argument('--nodel', action='store_true', help='do not scan for and delete extra files in destination directory')
del_args.add_argument('--askdel', action='store_true', help='ask whether to delete the extra files in destination directory (default)')
args = parser.parse_args()
real_run = not args.dry

# --- Load Profile Logic ---
supported_set = set()
mapping_dict = {}
    
# Locate the profile file in 'profiles/' directory relative to the script
profiles_path = Path(__file__).resolve().parent / 'profiles'
profile_file = profiles_path / args.profile if args.profile else None

# Checking if the profile file (if given) exists
if profile_file and not profile_file.exists():
    print(f"Error: Profile file '{args.profile}' not found in {profiles_path}")
    if args.profile == "default":
        print("\nPlease create it by symlinking or copying an existing profile, e.g.:")
        if os.name == 'nt':  # Windows
            print(r"  copy profiles\wiim profiles\default")
        else:                # Linux/macOS (ln is preferred)
            print("  (cd profiles && ln -s wiim default)")
            print("or")
            print("  cp profiles/wiim profiles/default")
    print('Available profiles:', ', '.join(f.name for f in profiles_path.iterdir() if f.is_file()))
    sys.exit(1)

# Load profile rules: first word is target, others map to it
if profile_file:
    supported_formats = set()
    change_extension = {}
    try:
        with open(profile_file, 'r') as f:    # maybe encoding='latin-1'?
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
if not Path(args.dst_dir).exists():
    print(f"Error: Destination directory '{args.dst_dir}' does not exist.")
    print("Please make sure your USB drive is mounted or the path is correct.")
    sys.exit(1)

playlist_filename = Path(args.playlist_filename)
dst_dir = Path(args.dst_dir)

def dst_file(src_file: Path) -> Path:   # destination file name (without path)
    if profile_file:
        src_file = src_file.with_suffix(src_file.suffix.lower())
        src_ext = src_file.suffix[1:]
        if src_ext in supported_formats:
            src_file = src_file.with_suffix('.' + change_extension.get(src_ext, src_ext))
        else:
            src_file = src_file.with_suffix('.mp3')
    return Path(src_file.name)

metadata = None
dsts = defaultdict(list)    # maps destination file name to source file name(s)
with open(playlist_filename) as f:
    for src_file in f:
        if src_file.startswith("#"):
            if src_file.startswith("#EXTINF:"): metadata = src_file
            continue
        src_file = (playlist_filename.parent / Path(src_file.strip()), metadata)
        metadata = None
        dsts[dst_file(src_file[0])].append(src_file)

to_del = set() if args.nodel else set(f.name for f in dst_dir.iterdir() if f.is_file())
dst_to_src = {}
skipped = 0
converted = 0
while dsts:
    dst_file_candidate, src_files = dsts.popitem()
    number = 1
    for src_file in src_files:
        dst_file = dst_file_candidate
        while dst_file in dsts or dst_file in dst_to_src:
            dst_file = dst_file.with_stem(dst_file_candidate.stem + str(number))
            number += 1
        dst_to_src[dst_file] = src_file
        to_del.discard(dst_file.name)
if args.lists > 0:
    for i in range(args.lists): to_del.discard(f'{i}.m3u')


def print_to_del():
    print(f'The destination directory contains {len(to_del)} extra files:')
    for to_del_file in to_del:
        print(quote(to_del_file), end=' ')
    print()

def delete_from_dst():
    global to_del
    l = len(to_del)
    print(f"Deleting {l} extra files from destination directory:")
    for idx, fname in enumerate(to_del, start=1):
        f = dst_dir / fname
        print(f"[{idx}/{l}] {f}")
        if real_run: f.unlink(missing_ok=True)
    to_del.clear()

# Suggests deleting extra files from destination:
if to_del:
    if args.autodel: delete_from_dst()
    else:
        print_to_del()
        while True:
            answer = input('Do you want to delete these files? [Y/N] ').lower()
            if answer in ['y', 'yes', 'n', 'no']: break
        if answer[0] == 'y': delete_from_dst()

total_files = len(dst_to_src)
skipped = 0
converted = 0
for idx, (dst_file, (src_file, metadata)) in enumerate(reversed(dst_to_src.items()), start=1):
    print(f"[{idx}/{total_files}] {src_file.name}",
        f" -> {dst_file.name}" if src_file.name != dst_file.name else '', sep='', end='')
    dst_file = dst_dir / dst_file
    to_copy = not profile_file or src_file.suffix[1:].lower() in supported_formats # file to be simply copied?
    
    def should_copy():
        try: dst_stat = dst_file.stat()
        except FileNotFoundError: return True   # destination does not exist
        src_stat = src_file.stat()
        if src_stat.st_mtime_ns > dst_stat.st_mtime_ns: return True # modification after last coping
        return to_copy and src_stat.st_size != dst_stat.st_size # file to copy differs in size

    if not args.replace and not should_copy():
        print("  (exists, skipped; use -r flag to overwrite)")
        skipped += 1
        continue
    else: print()
    if to_copy: # copy:
        if real_run: copyfile(src_file, dst_file)
    else:   # convert to mp3:
        if real_run: subprocess.run(["ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-i", str(src_file), "-codec:a", "libmp3lame", "-qscale:a", "2",
            "-map_metadata", "0:s:a:0", "-id3v2_version", "3", "-write_id3v1", "1",
            str(dst_file)])
        converted += 1

print(f'{len(dst_to_src)-converted-skipped} copied, {converted} transcoded, {skipped} skipped')

if args.lists > 0:
    print('Save playlists:', end='', flush=True)
    entries = [metadata + str(dst_file) if metadata else str(dst_file) for dst_file, (_, metadata) in reversed(dst_to_src.items())]

    def save_list(list_file_name):
        print('', list_file_name, end='', flush=True)
        if real_run:
            with open(dst_dir / list_file_name, 'w') as f:
                f.write('#EXTM3U\n')
                f.write('\n'.join(entries))

    save_list('0.m3u')
    from random import shuffle
    for i in range(1, args.lists):
        shuffle(entries)
        save_list(f'{i}.m3u')
    print()

if to_del: print_to_del()
