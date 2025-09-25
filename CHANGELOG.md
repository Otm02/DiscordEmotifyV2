# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [1.2.0] - 2025-09-25

- Security: Added a release automation script that signs the Windows executable (using a provided code-signing certificate) and emits SHA-256 checksum files for published artifacts.
- Build: Updated PyInstaller release workflow to bundle signed artifacts, compress them into `DiscordEmotify-vX.Y.Z-win64.zip`, and store matching `.sha256` manifests under `dist/`.
- Docs: Documented checksum verification, signature verification, and the new release script in the README.

[1.2.0]: https://github.com/Otm02/DiscordEmotifyV2/releases/tag/v1.2.0

## [1.0.0] - 2025-09-24

- First public release of DiscordEmotify V2
- Modern PyQt5 UI with Discord-like styling
- Friends view with DM ordering by recency and Group DM support
- Servers list with icons and channels grouped by categories
- Emoji input supports unicode, `:shortcode:`, `:custom_name:` auto-resolution, and `name:id`
- Start/Stop reacting with rate control and order (Newest → Oldest or Oldest → Newest)
- Option to clear reactions (unreact)
- Token save prompt with QSettings persistence
- Async image fetching and caching for smooth UI

[1.0.0]: https://github.com/Otm02/DiscordEmotifyV2/releases/tag/v1.0.0
 
## [1.0.1] - 2025-09-24

- Change: After connecting with a token, the app automatically opens the Friends section by default.
- Chore: Bump in-app version, embedded Windows file/product version, and packaging metadata to 1.0.1.

[1.0.1]: https://github.com/Otm02/DiscordEmotifyV2/releases/tag/v1.0.1

## [1.1.0] - 2025-09-24

- Feature: Support multiple emojis in the input field (separated by space or comma). The app will react sequentially with each emoji per message.
- Behavior: Rate limit (reactions/sec) applies to individual reactions, not in parallel, ensuring pacing per emoji per message.
- UX: Updated placeholder and hint to describe multi-emoji input.

[1.1.0]: https://github.com/Otm02/DiscordEmotifyV2/releases/tag/v1.1.0