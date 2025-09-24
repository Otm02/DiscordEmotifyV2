## How to Retrieve Your Discord User Token (Chrome Example)

> IMPORTANT: Your user token is a secret. Anyone with it can fully control your account. Never share it, never commit it to version control, and prefer using an official **Bot Token** (via the Discord Developer Portal) whenever possible. Using a user token for automation likely violates Discord's Terms of Service and can get your account disabled. Proceed only if you understand the risks.

### 1. Consider a Safer Alternative First

If you just need to react to messages programmatically, the compliant approach is to:
1. Create an application & bot in the Discord Developer Portal.
2. Invite the bot to your server with appropriate permissions.
3. Use the bot token instead of a user token (this app currently expects a user token, so you'd need to adapt code for the bot API if you go that route).

### 2. Chrome (or any Chromium-based browser) Steps

1. Open Discord in your browser: https://discord.com/app
2. Log in (if you are not already).
3. Press `F12` (or `Ctrl+Shift+I`) to open Developer Tools.
4. Go to the `Network` tab.
5. In the Network filter box, type `messages` (this narrows requests to message endpoints).
6. Click on any friend, group, or channel so a message-related request appears (e.g., scroll a channel or send a message so a `messages` or `.../messages?limit=` request appears).
7. Click one of the `messages` requests (often named something like `messages?limit=50`).
8. In the right panel, select the `Headers` tab.
9. In `Request Headers`, locate the `Authorization` header.
10. Copy the entire value (it will look like a long base64-like string). This is your user token.

### 3. Firefox Steps (Optional)

1. Open Discord in Firefox.
2. Press `F12` to open DevTools, choose the `Network` tab.
3. Filter or look for a `messages` request after interacting with a channel.
4. Select the request, go to `Headers`, then find `Authorization` under Request Headers.
5. Copy its value.

### 4. Keep It Secure

Suggested practices:
* Do NOT paste it into screenshots or share it.
* Avoid storing it in plaintext. Options:
  * Set an environment variable (e.g., on Windows PowerShell: `setx DISCORD_USER_TOKEN "<token>"`). Re-open the terminal afterward.
  * Create a local `.env` file (ensure it is in `.gitignore`) and load it in code if you modify the application.
* If you suspect compromise, change your Discord password (this will invalidate existing tokens) and re-login.

### 5. Troubleshooting

| Issue                               | Possible Cause                          | Fix                                                                  |
| ----------------------------------- | --------------------------------------- | -------------------------------------------------------------------- |
| No `messages` requests appear       | Filter too strict or no recent activity | Clear filter, trigger activity (scroll channel / send a message)     |
| No `Authorization` header visible   | Selected the wrong request type         | Ensure it's a REST API request (not a CDN/static asset)              |
| Token starts with `Bot `            | That's a bot token, not a user token    | The app expects a raw user token (again, using user tokens is risky) |
| 401 / Unauthorized when using token | Token expired or password changed       | Retrieve a fresh token after re-login                                |

### 6. Ethical & Legal Notice

Automating user accounts (self-bots) is disallowed by Discord's Terms of Service. This guide is provided purely for educational context. Use responsibly and at your own risk. Prefer official bot integrations.

### 7. Next Steps

After copying the token, paste it into the application when prompted. Then proceed with server / channel selection and reacting. See the main `README.md` for usage details.
