#!/usr/bin/python3

from shutil import copyfile
from pathlib import Path
from collections import defaultdict
import subprocess
import argparse

parser = argparse.ArgumentParser(prog='cp_playlist',
                    description='Copy music files from playlist to given directory.')
parser.add_argument('playlist_filename', help='file name of m3u playlist')
parser.add_argument('dst_dir', help='destination directory')
parser.add_argument('-r', '--replace', action='store_true', help='whether to replace destination files if they already exist')
args = parser.parse_args()

supported_formats = {"mp3", "wma", "aac", "m4a", "mp4", "flac", "wav", "aif", "aiff", "alac"} # "wave", "mp4"
change_extension = {'opus': 'ogg'}  # all these are also supported
for (ext1, ext2) in change_extension.items():
    supported_formats.insert(ext1)
    supported_formats.insert(ext2)

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
        while dst_file in dsts or dst_file in copied:
            dst_file = dst_file.with_stem(dst_file_candidate.stem + str(number))
            number += 1
        copied.add(dst_file)
        print(f"[{len(copied)}/{total_files}] {src_file.name}",
            f" -> {dst_file.name}" if src_file.name != dst_file.name else '', sep='')
        dst_file = dst_dir / dst_file
        if not args.replace and dst_file.exists():
            print("  destination file exists, skipped (run with -r flag to overwrite)")
            skipped += 1
            continue
        if src_file.suffix[1:].lower() in supported_formats: # copy:
            copyfile(src_file, dst_file)
        else:   # convert to mp3:
            subprocess.run(["ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-i", str(src_file), "-codec:a", "libmp3lame", "-qscale:a", "2",
                "-map_metadata", "0:s:a:0", "-id3v2_version", "3", "-write_id3v1", "1",
                str(dst_file)])
            converted += 1
print(f'{len(copied)} processed, {converted} converted, {skipped} skipped')
