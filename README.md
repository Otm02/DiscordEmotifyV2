# DiscordEmotify

A desktop app to react with emojis or emotes to all messages in a selected Discord channel or DM.

## Features

- Enter your Discord user token
- Select servers (displayed as list, click to show channels)
- Select friends (click to open DM)
- Choose an emoji or emote (enter in text field, for custom emotes use name:id)
- React to all recent messages in the selected channel

## Installation

1. Install Python 3.x
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python DiscordEmotify.py`

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