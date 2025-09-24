# DiscordEmotify

A desktop app to react with emojis or emotes to all messages in a selected Discord channel or DM.

## Features

- Enter your Discord user token
- Select servers (displayed as list, click to show channels)
- Select friends (click to open DM)
- Choose an emoji or emote (enter in text field, for custom emotes use name:id)
- React to all recent messages in the selected channel

## Installation (from source)

1. Install Python 3.x
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python DiscordEmotify.py`

## Versioning

The app follows SemVer. Current version is displayed in the window title and about text.

See `CHANGELOG.md` for details on each release.

## Usage

1. Enter your Discord token (get from browser dev tools, Authorization header)
2. Click Connect
3. Click on "Friends" or a server to see channels/DMs
4. Click on a channel or friend
5. Enter emoji:
	- Press `Windows + .` (Win key and period) to open the built‑in emoji picker on Windows
	- Type a direct unicode emoji (e.g. 😀)
	- Type `:smile:` or any standard shortcode (resolved via the `emoji` library if installed)
	- Type `:custom_name:` to auto-resolve a custom guild emoji (falls back across your guilds)
	- Or provide explicit custom format `name:id` if you know the emoji ID
6. Click "React to All Messages" (Start / Stop toggle)

Note: Using user tokens for automation may violate Discord TOS. Use at your own risk.

### Getting Your Token

For a detailed, step-by-step illustrated explanation of how to locate your `Authorization` header in the browser developer tools, see: [How to Retrieve Your Discord User Token](./HOW_TO_GET_TOKEN.md). Strongly consider using a bot token instead; user-token automation can breach Discord's Terms of Service.

## Tips & Notes

* Use `Windows + .` to quickly pick any unicode emoji.
* The field accepts unicode, `:shortcode:` style, `:custom_name:` (auto search), or `name:id`.
* Order and rate controls let you tune API pacing; respect Discord rate limits.

## Limitations

* No integrated graphical emoji picker beyond system shortcut.
* Large-scale reacting may hit Discord's rate limits or violate ToS.
* Use responsibly.

## Build a Windows release (PyInstaller)

Prerequisites:

- Python 3.9+ on Windows
- Dependencies installed: `pip install -r requirements.txt`
- PyInstaller installed: `pip install pyinstaller`

Build steps:

1. From the project root, run:

	````powershell
	pyinstaller --clean --noconfirm .\DiscordEmotify.spec
	```

2. The executable will be at `dist\DiscordEmotify\DiscordEmotify.exe`.

3. Zip the `dist\DiscordEmotify` folder contents for a GitHub Release asset, e.g. `DiscordEmotify-v1.0.0-win64.zip`.

Notes:

- Icons and resources are bundled.
- The version info resource is embedded from `version_info.txt`. Update the version in that file and in `DiscordEmotify.py` (`__version__`) for a new release.
- When running as a one-file bundle (`--onefile`), the included `resource_path` helper locates assets correctly. The provided spec uses a folder bundle for easier AV compatibility; you can switch to onefile by replacing `COLLECT` with a `onefile` `EXE` in the spec if desired.