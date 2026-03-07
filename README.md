# cpls (Copy PlayList)

`cpls` is a minimalist Python-based CLI tool for copying music files from playlists to USB drives or external devices.
It intelligently handles path resolution, file format mapping, and automatic transcoding.

## Example Usage
```bash
python cpls.py music.m3u /media/usb-drive/
```

To see all available options:
```bash
python cpls.py --help
```

## Features

- **Playlist Support:** Tool for parsing `.m3u`, `.m3u8`, and simple `.txt` files (one file path per line).
- **Metadata Awareness:** Automatically skips lines starting with `#` (e.g., `#EXTINF` metadata) and empty lines.
- **Context-Aware Paths:** Full support for relative paths, resolved against the playlist file's location.
- **Device Profiles:** Use profile files in the `profiles/` directory to define hardware compatibility.
- **Extension Mapping:** Tool for renaming extensions based on profile rules (e.g., `ogg opus` maps `.opus` files to `.ogg`).
- **Auto-Transcoding:** Automatically converts any unsupported formats to **MP3** via **ffmpeg**.

## Requirements

- **Python 3.x**
- **ffmpeg** (must be available in your system PATH for transcoding)

## How Device Profiles Work

Profiles are stored as text files in the `profiles/` directory. The program parses them line by line:

1. **Single extension per line:** The format is considered supported (e.g., `flac`).
2. **Multiple extensions per line:** If a line contains multiple extensions (e.g., `ogg opus`), files using any of the subsequent extensions will be remapped to the **first** one in that line.
3. **Automatic Conversion:** Any file extension not listed in the active device profile is automatically transcoded to **MP3** using `ffmpeg`.

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. See the [LICENSE](LICENSE) file for the full text.
