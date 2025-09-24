import sys
import os
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QComboBox,
    QCheckBox,
    QProgressBar,
    QSpinBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QSettings, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QDesktopServices
import requests
import urllib.parse
import threading
import time
import re

try:
    import emoji as emoji_lib
except Exception:
    emoji_lib = None

# ---------------- Versioning & App metadata -----------------
APP_NAME = "DiscordEmotify"
__version__ = "1.1.0"
REPO_URL = "https://github.com/Otm02/DiscordEmotifyV2"
USER_AGENT = f"{APP_NAME}/{__version__} (+{REPO_URL})"


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for development and for PyInstaller bundled app.
    When bundled, PyInstaller sets sys._MEIPASS to the temp folder containing extracted files.
    """
    try:
        base_path = getattr(sys, "_MEIPASS")  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


DISCORD_BG = "#2f3136"
DISCORD_SIDEBAR = "#202225"
DISCORD_ELEVATED = "#36393f"
DISCORD_TEXT = "#dcddde"
DISCORD_MUTED = "#b9bbbe"
DISCORD_ACCENT = "#5865F2"


def circular_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    if pixmap.isNull():
        return QPixmap()
    img = pixmap.scaled(
        size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)
    p = QPainter(rounded)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.setClipPath(path)
    p.drawPixmap(0, 0, img)
    p.end()
    return rounded


class DiscordEmotify(QWidget):
    # Signals for thread-safe UI updates
    sig_status = pyqtSignal(str)  # update status label
    sig_running = pyqtSignal(
        bool
    )  # update running state (button text/checked and internal flag)
    sig_guilds_loaded = pyqtSignal(list)
    sig_friends_loaded = pyqtSignal(list)
    sig_channels_loaded = pyqtSignal(str, list)  # guild_id, channels
    sig_image_loaded = pyqtSignal(str, object)  # key, raw bytes
    sig_error = pyqtSignal(str)  # display an error message in UI

    def __init__(self):
        super().__init__()
        self.token = ""
        self.selected_channel = None
        self.selected_context_name = ""
        self.selected_emoji = ""
        self.current_guild_id = None
        self.selected_guild_id = None
        self._guilds = []
        self._emoji_cache_by_guild = {}
        # Performance: reuse a single HTTP session, set timeouts, and cache images
        self._timeout = 15
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": USER_AGENT})
        self._img_cache = {}
        self._reacting = False
        self._pending_guild_for_load = None
        self._img_waiters = {}
        self._img_loading = set()
        # Connect signals
        self.sig_status.connect(self._on_status)
        self.sig_running.connect(self._on_running_change)
        self.sig_guilds_loaded.connect(self._on_guilds_loaded)
        self.sig_friends_loaded.connect(self._on_friends_loaded)
        self.sig_channels_loaded.connect(self._on_channels_loaded)
        self.sig_image_loaded.connect(self._on_image_loaded)
        self.sig_error.connect(self._on_error)
        # Persistent settings (registry on Windows, ini on others) created before UI so handlers can use it immediately
        self.settings = QSettings("DiscordEmotify", "DiscordEmotifyApp")
        self._build_ui()
        try:
            saved_token = self.settings.value("token", "", type=str)
            if saved_token:
                self.token_edit.setText(saved_token)
            ask_flag = self.settings.value("askSaveToken", True, type=bool)
            if hasattr(self, "ask_save_checkbox"):
                self.ask_save_checkbox.setChecked(bool(ask_flag))
        except Exception:
            pass

    # ---------------- Token persistence prompt -----------------
    def _maybe_prompt_save_token(self, token: str):
        """Offer to save token locally (QSettings).
        Dialog contains Yes / No buttons and a 'Don't show this again' checkbox.
        Only shown if askSaveToken flag is True and token differs from saved one.
        """
        if not token:
            return
        try:
            ask_flag = self.settings.value("askSaveToken", True, type=bool)
        except Exception:
            ask_flag = True
        if not ask_flag:
            return
        try:
            existing = self.settings.value("token", "", type=str)
        except Exception:
            existing = ""
        if existing == token:
            return
        # Build dialog
        box = QMessageBox(self)
        box.setWindowTitle("Save Token?")
        box.setIcon(QMessageBox.Question)
        box.setText(
            "Save your Discord token locally so you don't have to paste it next time?\n"
            "Only do this on a private, trusted device."
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        cb = QCheckBox("Don't show this again")
        box.setCheckBox(cb)
        result = box.exec_()
        dont_show = cb.isChecked()
        try:
            if result == QMessageBox.Yes:
                self.settings.setValue("token", token)
            if dont_show:
                self.settings.setValue("askSaveToken", False)
                if hasattr(self, "ask_save_checkbox"):
                    self.ask_save_checkbox.setChecked(False)
        except Exception:
            pass

    def _on_status(self, text: str):
        self.status_label.setText(text)

    def _on_running_change(self, running: bool):
        self._reacting = running
        self.react_btn.setChecked(running)
        self.react_btn.setText("Stop" if running else "Start")
        if not running:
            self.status_label.setText("Idle")

    def _on_error(self, text: str):
        # Highlight error in status label
        self.status_label.setStyleSheet("color: #ff6b6b;")
        self.status_label.setText(f"Error: {text}")

        # Revert color after short delay so future normal statuses look fine
        def _restore():
            time.sleep(4)
            try:
                # Only restore if message unchanged (avoid racing with new status)
                if self.status_label.text() == f"Error: {text}":
                    self.status_label.setStyleSheet("color: #b9bbbe;")
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()

    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        # Set window icon from local DiscordEmotify.ico
        try:
            app_icon_path = resource_path("DiscordEmotify.ico")
            if os.path.exists(app_icon_path):
                self.setWindowIcon(QIcon(app_icon_path))
        except Exception:
            pass
        self.resize(1024, 700)

        # Global style (Discord-like)
        self.setStyleSheet(
            f"""
            QWidget {{ background: {DISCORD_BG}; color: {DISCORD_TEXT}; }}
            QLineEdit {{ background: {DISCORD_ELEVATED}; border: 1px solid #000; padding: 6px; border-radius: 6px; color: {DISCORD_TEXT}; }}
            QPushButton {{ background: {DISCORD_ACCENT}; color: white; border: none; padding: 8px 12px; border-radius: 6px; }}
            QPushButton:hover {{ background: #4752C4; }}
            QListWidget {{ background: {DISCORD_ELEVATED}; border: none; }}
            QListWidget::item {{ padding: 8px; }}
            QListWidget::item:selected {{ background: #4f545c; border-radius: 6px; }}
            QLabel#muted {{ color: {DISCORD_MUTED}; }}

            /* Thin Discord-esque vertical scrollbar for channels list */
            #channelsList QScrollBar:vertical {{
                background: {DISCORD_ELEVATED};
                width: 8px;
                margin: 0px;
            }}
            #channelsList QScrollBar::handle:vertical {{
                background: #4f545c;
                min-height: 24px;
                border-radius: 4px;
            }}
            #channelsList QScrollBar::handle:vertical:hover {{
                background: #5d626a;
            }}
            #channelsList QScrollBar::add-line:vertical,
            #channelsList QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
            #channelsList QScrollBar::add-page:vertical,
            #channelsList QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            /* Mirror the same style for the channels tree */
            #channelsTree QScrollBar:vertical {{
                background: {DISCORD_ELEVATED};
                width: 8px;
                margin: 0px;
            }}
            #channelsTree QScrollBar::handle:vertical {{
                background: #4f545c;
                min-height: 24px;
                border-radius: 4px;
            }}
            #channelsTree QScrollBar::handle:vertical:hover {{
                background: #5d626a;
            }}
            #channelsTree QScrollBar::add-line:vertical,
            #channelsTree QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
            #channelsTree QScrollBar::add-page:vertical,
            #channelsTree QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            /* Larger font & padding for friends/channels list */
            #channelsTree {{ font-size: 12pt; }}
            #channelsTree::item {{ padding: 8px 6px; }}
        """
        )

        root = QVBoxLayout(self)

        # Top bar for token + connect
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Token:"))
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Paste your Discord user token…")
        # Hide token input characters
        self.token_edit.setEchoMode(QLineEdit.Password)
        top_bar.addWidget(self.token_edit, 1)
        # Help button linking to official token instructions
        self.token_help_btn = QPushButton("?")
        self.token_help_btn.setFixedWidth(28)
        self.token_help_btn.setToolTip(
            "Open token retrieval instructions (official repo)"
        )
        self.token_help_btn.clicked.connect(self._open_token_help)
        top_bar.addWidget(self.token_help_btn)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect)
        top_bar.addWidget(self.connect_btn)
        self.forget_btn = QPushButton("Forget")
        self.forget_btn.setToolTip("Clear the stored token and re-enable save prompt")
        self.forget_btn.clicked.connect(self._forget_token)
        top_bar.addWidget(self.forget_btn)
        # Ask-to-save toggle
        self.ask_save_checkbox = QCheckBox("Ask to save")
        self.ask_save_checkbox.setToolTip(
            "Toggle whether the app prompts to save the token"
        )
        self.ask_save_checkbox.stateChanged.connect(self._on_ask_save_changed)
        top_bar.addWidget(self.ask_save_checkbox)
        root.addLayout(top_bar)

        # Thin horizontal loading bar (indeterminate) under the token row
        self.loading_bar = QProgressBar()
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setRange(0, 0)  # indeterminate
        self.loading_bar.setVisible(False)
        self.loading_bar.setStyleSheet(
            f"QProgressBar {{ background: {DISCORD_ELEVATED}; border: none; }}"
            f" QProgressBar::chunk {{ background: {DISCORD_ACCENT}; }}"
        )
        root.addWidget(self.loading_bar)

        # Splitter: [servers sidebar] | [friends/channels list] | [actions]
        splitter = QSplitter(Qt.Horizontal)

        # Left servers bar
        left_wrap = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setStyleSheet(f"background:{DISCORD_SIDEBAR};")
        self.servers_list = QListWidget()
        self.servers_list.setViewMode(QListWidget.IconMode)
        self.servers_list.setMovement(QListWidget.Static)
        self.servers_list.setFlow(QListWidget.TopToBottom)
        self.servers_list.setIconSize(QSize(48, 48))
        self.servers_list.setSpacing(10)
        self.servers_list.setResizeMode(QListWidget.Adjust)
        self.servers_list.setUniformItemSizes(True)
        self.servers_list.setWordWrap(False)
        self.servers_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Hide vertical scrollbar but keep wheel scrolling (Discord-like)
        self.servers_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Ensure vertical flow with no wrapping
        self.servers_list.setWrapping(False)
        self.servers_list.setFixedWidth(90)
        self.servers_list.itemClicked.connect(self.on_server_click)
        left_wrap.addWidget(self.servers_list)
        left_widget.setLayout(left_wrap)

        # Middle list (friends or channels with collapsible categories)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        header = QHBoxLayout()
        self.context_label = QLabel("Select Friends or a Server")
        header.addWidget(self.context_label, 1)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search…")
        self.search_edit.textChanged.connect(self._filter_middle_list)
        header.addWidget(self.search_edit)
        middle_layout.addLayout(header)

        self.channels_tree = QTreeWidget()
        self.channels_tree.setObjectName("channelsTree")
        self.channels_tree.setHeaderHidden(True)
        self.channels_tree.setIconSize(QSize(32, 32))
        self.channels_tree.itemClicked.connect(self.on_tree_item_click)
        middle_layout.addWidget(self.channels_tree, 1)

        # Right actions panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Emoji to react with:"))
        self.emoji_edit = QLineEdit()
        # Updated placeholder to guide users about multiple entries and syntax
        self.emoji_edit.setPlaceholderText(
            "😀 :emoji: name:id  (separate multiple with space or comma)"
        )
        right_layout.addWidget(self.emoji_edit)
        # Small hint label (muted style) below the input
        emoji_hint = QLabel(
            "Tip: Press Windows + . (Win key + period) to open the system emoji picker. "
            "You can enter multiple emojis separated by space or comma. Supports unicode, :shortcode:, :custom_name:, and name:id."
        )
        emoji_hint.setWordWrap(True)
        emoji_hint.setObjectName("muted")
        right_layout.addWidget(emoji_hint)
        # Options row: order and clear/unreact
        opts1 = QHBoxLayout()
        opts1.addWidget(QLabel("Order:"))
        self.order_combo = QComboBox()
        self.order_combo.addItems(["Newest → Oldest", "Oldest → Newest"])
        opts1.addWidget(self.order_combo, 1)
        right_layout.addLayout(opts1)

        self.clear_checkbox = QCheckBox("Clear reactions (unreact)")
        right_layout.addWidget(self.clear_checkbox)

        # Rate control
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Reactions/sec:"))
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(1, 20)
        self.rate_spin.setValue(1)  # default to 1 rps
        rate_row.addWidget(self.rate_spin)
        rate_row.addStretch(1)
        right_layout.addLayout(rate_row)

        # Max messages limit
        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max messages (0 = all):"))
        self.max_messages_spin = QSpinBox()
        self.max_messages_spin.setRange(0, 1_000_000)
        self.max_messages_spin.setValue(0)
        max_row.addWidget(self.max_messages_spin)
        max_row.addStretch(1)
        right_layout.addLayout(max_row)

        # Start/Stop toggle
        self.react_btn = QPushButton("Start")
        self.react_btn.setCheckable(True)
        self.react_btn.clicked.connect(self._toggle_reacting)
        right_layout.addWidget(self.react_btn)

        # Status label
        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("muted")
        right_layout.addWidget(self.status_label)
        right_layout.addStretch(1)
        disclaimer = QLabel(
            "Only use this app if you obtained it from the official repository:\n"
            f"{REPO_URL}\n"
            f"By Athmane Benarous — v{__version__}"
        )
        disclaimer.setObjectName("muted")
        disclaimer.setWordWrap(True)
        right_layout.addWidget(disclaimer)

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(middle_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([90, 700, 250])
        root.addWidget(splitter, 1)

    def _forget_token(self):
        """Clear stored token and re-enable prompt."""
        try:
            self.settings.remove("token")
            self.settings.setValue("askSaveToken", True)
        except Exception:
            pass
        self.token = ""
        self.token_edit.clear()
        self.sig_status.emit("Token cleared")

    def _on_ask_save_changed(self, state: int):
        try:
            self.settings.setValue("askSaveToken", bool(state))
        except Exception:
            pass

    def _filter_middle_list(self, text: str):
        text = text.strip().lower()

        # Filter for tree: show categories if any child matches, hide non-matching items
        def filter_item(item: QTreeWidgetItem) -> bool:
            match = text in item.text(0).lower()
            if item.childCount() == 0:
                item.setHidden(not match)
                return match
            any_child_visible = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    any_child_visible = True
            item.setHidden(not (match or any_child_visible))
            return not item.isHidden()

        root_count = self.channels_tree.topLevelItemCount()
        for i in range(root_count):
            filter_item(self.channels_tree.topLevelItem(i))

    def _headers(self):
        return {"Authorization": self.token}

    def _set_loading(self, on: bool):
        # Show/hide the indeterminate loading bar and flush UI for immediate feedback
        self.loading_bar.setVisible(on)
        if on:
            self.loading_bar.setRange(0, 0)
            QApplication.processEvents()
        else:
            # Switch to determinate completed state to clear the busy animation cleanly
            self.loading_bar.setRange(0, 1)
            self.loading_bar.setValue(1)

    def _default_circular_icon(self, size: int = 48) -> QPixmap:
        # Try to load discord_icon.ico from workspace; fall back to a white circle
        icon_path = resource_path("discord_icon.ico")
        pm = QPixmap()
        if os.path.exists(icon_path):
            pm = QPixmap(icon_path)
            if not pm.isNull():
                return circular_pixmap(pm, size)
        # Fallback simple circle
        base = QPixmap(size, size)
        base.fill(Qt.transparent)
        p = QPainter(base)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(Qt.white)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, size, size)
        p.end()
        return base

    # --- Emoji resolution helpers ---
    def _get_guild_emojis(self, guild_id: str):
        if not guild_id:
            return []
        if guild_id in self._emoji_cache_by_guild:
            return self._emoji_cache_by_guild[guild_id]
        try:
            r = self.http.get(
                f"https://discord.com/api/v10/guilds/{guild_id}/emojis",
                headers=self._headers(),
                timeout=self._timeout,
            )
            emojis = r.json() if r.ok else []
            self._emoji_cache_by_guild[guild_id] = emojis
            return emojis
        except Exception:
            return []

    def _find_custom_emoji(self, name: str, preferred_guild_id: str = None) -> str:
        # Search preferred guild first
        candidate = None
        if preferred_guild_id:
            for e in self._get_guild_emojis(preferred_guild_id):
                if str(e.get("name", "")).lower() == name.lower():
                    candidate = f"{e.get('name')}:{e.get('id')}"
                    return candidate
        # Fallback: search across all known guilds (may be slower the first time)
        for g in getattr(self, "_guilds", []):
            gid = str(g.get("id"))
            if preferred_guild_id and gid == str(preferred_guild_id):
                continue
            for e in self._get_guild_emojis(gid):
                if str(e.get("name", "")).lower() == name.lower():
                    return f"{e.get('name')}:{e.get('id')}"
        return None

    def _resolve_emoji_for_api(self, text: str, guild_id: str = None) -> str:
        # If input is like :name:, try unicode first via emoji library, else treat as custom name
        m = re.fullmatch(r":([A-Za-z0-9_]+):", text)
        if m:
            name = m.group(1)
            # Try to resolve to unicode emoji using emoji library if available
            if emoji_lib is not None:
                try:
                    uni = emoji_lib.emojize(f":{name}:")
                    if uni and uni != f":{name}:":
                        return uni
                except Exception:
                    pass
            # Otherwise, attempt to resolve as custom server emoji
            custom = self._find_custom_emoji(name, preferred_guild_id=guild_id)
            if custom:
                return custom
            return None
        # If it isn't :name: form, assume user entered either unicode emoji or name:id format already
        return text

    def _fetch_pixmap(self, url: str, size: int = 48, circular: bool = True) -> QPixmap:
        try:
            cache_key = f"{size}:{1 if circular else 0}:{url}"
            if cache_key in self._img_cache:
                return self._img_cache[cache_key]
            r = self.http.get(url, timeout=self._timeout)
            pm = QPixmap()
            if r.status_code == 200:
                pm.loadFromData(r.content)
                if circular:
                    pm = circular_pixmap(pm, size)
                else:
                    pm = pm.scaled(
                        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                self._img_cache[cache_key] = pm
                return pm
        except Exception:
            pass
        return QPixmap()

    def _fetch_pixmap_async(
        self,
        url: str,
        size: int,
        circular: bool,
        target,
        target_kind: str,
        column: int = 0,
    ):
        key = f"{size}:{1 if circular else 0}:{url}"
        # If cached, update immediately
        if key in self._img_cache:
            pm = self._img_cache[key]
            if target_kind == "server":
                target.setIcon(QIcon(pm))
            elif target_kind == "tree":
                target.setIcon(column, QIcon(pm))
            return
        # Register waiter
        self._img_waiters.setdefault(key, []).append((target_kind, target, column))
        # Already loading
        if key in self._img_loading:
            return
        self._img_loading.add(key)

        def worker(fetch_url: str, k: str):
            try:
                sess = requests.Session()
                sess.headers.update({"User-Agent": USER_AGENT})
                r = sess.get(fetch_url, timeout=self._timeout)
                data = r.content if r.status_code == 200 else b""
                self.sig_image_loaded.emit(k, data)
            except Exception:
                self.sig_image_loaded.emit(k, b"")

        threading.Thread(target=lambda: worker(url, key), daemon=True).start()

    def _on_image_loaded(self, key: str, data: bytes):
        waiters = self._img_waiters.pop(key, [])
        self._img_loading.discard(key)
        if not waiters:
            return
        pm = QPixmap()
        try:
            if data:
                # Parse key
                try:
                    size_str, circ_str, url = key.split(":", 2)
                    size = int(size_str)
                    circular = circ_str == "1"
                except Exception:
                    size, circular = 48, True
                pm.loadFromData(data)
                if circular:
                    pm = circular_pixmap(pm, size)
                else:
                    pm = pm.scaled(
                        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                self._img_cache[key] = pm
        except Exception:
            pm = QPixmap()
        # Update all targets
        for kind, target, col in waiters:
            if pm.isNull():
                continue
            if kind == "server":
                target.setIcon(QIcon(pm))
            elif kind == "tree":
                target.setIcon(col, QIcon(pm))

    def connect(self):
        self.token = self.token_edit.text().strip()
        if not self.token:
            return
        # Offer to save before making network calls (only once per new token)
        self._maybe_prompt_save_token(self.token)
        self.servers_list.clear()
        self.channels_tree.clear()

        # Add a "Friends" pill at the top
        friends_item = QListWidgetItem()
        friends_item.setToolTip("Friends")
        # Use discord_icon.ico for friends icon if available, circularized
        friends_item.setIcon(QIcon(self._default_circular_icon(48)))
        friends_item.setData(Qt.UserRole, "friends")
        friends_item.setSizeHint(QSize(60, 60))
        self.servers_list.addItem(friends_item)
        # Auto-select and open Friends by default
        try:
            self.servers_list.setCurrentItem(friends_item)
            self.on_server_click(friends_item)
        except Exception:
            pass

        self._set_loading(True)

        # Fetch guilds in background
        def _load_guilds():
            try:
                sess = requests.Session()
                sess.headers.update({"User-Agent": USER_AGENT})
                r = sess.get(
                    "https://discord.com/api/v10/users/@me/guilds",
                    headers=self._headers(),
                    timeout=self._timeout,
                )
                if r.status_code == 401:
                    self.sig_error.emit("Invalid token (401)")
                    self.sig_guilds_loaded.emit([])
                    return
                if r.status_code == 403:
                    self.sig_error.emit("Forbidden loading guilds (403)")
                    self.sig_guilds_loaded.emit([])
                    return
                guilds = r.json() if r.ok else []
                # Try to fetch user settings to get real server (guild) order
                try:
                    rs = sess.get(
                        "https://discord.com/api/v10/users/@me/settings",
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                    if rs.status_code == 401:
                        self.sig_error.emit("Invalid token while loading settings")
                        self.sig_guilds_loaded.emit([])
                        return
                    if rs.status_code == 403:
                        self.sig_error.emit("Forbidden loading settings (403)")
                    settings = rs.json() if rs.ok else {}
                except Exception:
                    settings = {}
                positions = settings.get("guild_positions") or []
                if not positions and isinstance(settings.get("guild_folders"), list):
                    # Fallback: flatten folder order into a positions list
                    flat = []
                    for f in settings.get("guild_folders", []):
                        gids = f.get("guild_ids") or []
                        flat.extend(gids)
                    positions = flat
                if positions:
                    order_index = {str(gid): i for i, gid in enumerate(positions)}
                    guilds.sort(key=lambda g: order_index.get(str(g.get("id")), 10**9))
                self.sig_guilds_loaded.emit(guilds)
            except Exception as e:
                print("Failed to load guilds:", e)
                self.sig_guilds_loaded.emit([])

        threading.Thread(target=_load_guilds, daemon=True).start()

    def on_server_click(self, item: QListWidgetItem):
        guild_id = item.data(Qt.UserRole)
        self.channels_tree.clear()
        if guild_id == "friends":
            self.selected_guild_id = None
            self.context_label.setText("Friends")
            self._set_loading(True)

            def _load_friends():
                try:
                    sess = requests.Session()
                    sess.headers.update({"User-Agent": USER_AGENT})
                    # Fetch friend relationships
                    rel_resp = sess.get(
                        "https://discord.com/api/v10/users/@me/relationships",
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                    if rel_resp.status_code in (401, 403):
                        self.sig_error.emit(
                            "Invalid token (401)"
                            if rel_resp.status_code == 401
                            else "Forbidden loading friends (403)"
                        )
                        self.sig_friends_loaded.emit([])
                        return
                    relationships = rel_resp.json() if rel_resp.ok else []
                    # Build map of friend user objects
                    friend_users = {
                        f["user"]["id"]: f["user"]
                        for f in relationships
                        if f.get("type") == 1 and isinstance(f.get("user"), dict)
                    }
                    # Fetch DM channels (includes open DMs & groups) to extract last interaction ordering
                    dm_resp = sess.get(
                        "https://discord.com/api/v10/users/@me/channels",
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                    dm_channels = dm_resp.json() if dm_resp.ok else []

                    # Merge direct & group DMs; sort by recency (last_message_id desc) to mirror Discord ordering.
                    def _lm_id(chan):
                        lm = chan.get("last_message_id")
                        try:
                            return int(lm)
                        except Exception:
                            return 0

                    all_dms = [c for c in dm_channels if c.get("type") in (1, 3)]
                    all_dms.sort(key=_lm_id, reverse=True)

                    ordered_entries = []
                    seen_user_ids = set()
                    for dm in all_dms:
                        ctype = dm.get("type")
                        if ctype == 1:
                            recips = dm.get("recipients") or []
                            if not recips:
                                continue
                            user = recips[0]
                            uid = user.get("id")
                            if not uid:
                                continue
                            seen_user_ids.add(uid)
                            base_user = friend_users.get(uid, user)
                            ordered_entries.append(
                                {
                                    "type": 1,
                                    "user": base_user,
                                    "dm_channel_id": dm.get("id"),
                                    "_last_message_id": dm.get("last_message_id"),
                                }
                            )
                        elif ctype == 3:
                            recips = dm.get("recipients") or []
                            name = dm.get("name")
                            if not name:
                                usernames = [r.get("username", "?") for r in recips][:3]
                                name = ", ".join(usernames) or "Group DM"
                                if len(recips) > 3:
                                    name += ", …"
                            ordered_entries.append(
                                {
                                    "is_group": True,
                                    "group_name": name,
                                    "dm_channel_id": dm.get("id"),
                                    "icon": dm.get("icon"),
                                    "_last_message_id": dm.get("last_message_id"),
                                }
                            )

                    # Remaining friends with no DM channel yet appear after existing DM threads.
                    for uid, user in friend_users.items():
                        if uid in seen_user_ids:
                            continue
                        ordered_entries.append({"type": 1, "user": user})
                    self.sig_friends_loaded.emit(ordered_entries)
                except Exception as e:
                    print("Failed to load friends:", e)
                    self.sig_friends_loaded.emit([])

            threading.Thread(target=_load_friends, daemon=True).start()
        else:
            # Track selected guild id for emoji resolution
            self.selected_guild_id = str(guild_id)
            self.context_label.setText("Channels")
            self._set_loading(True)
            self._pending_guild_for_load = str(guild_id)

            def _load_channels(gid: str):
                try:
                    sess = requests.Session()
                    sess.headers.update({"User-Agent": USER_AGENT})
                    r = sess.get(
                        f"https://discord.com/api/v10/guilds/{gid}/channels",
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                    if r.status_code == 401:
                        self.sig_error.emit("Invalid token (401)")
                        self.sig_channels_loaded.emit(gid, [])
                        return
                    if r.status_code == 403:
                        self.sig_error.emit("Forbidden loading channels (403)")
                        self.sig_channels_loaded.emit(gid, [])
                        return
                    channels = r.json() if r.ok else []
                    self.sig_channels_loaded.emit(gid, channels)
                except Exception as e:
                    print("Failed to load channels:", e)
                    self.sig_channels_loaded.emit(gid, [])

            threading.Thread(
                target=lambda: _load_channels(str(guild_id)), daemon=True
            ).start()

    def _on_guilds_loaded(self, guilds: list):
        try:
            self._guilds = guilds or []
            for guild in guilds:
                item = QListWidgetItem()
                item.setToolTip(guild.get("name", ""))
                if guild.get("icon"):
                    icon_url = f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=64"
                    # async load icon to avoid blocking UI
                    self._fetch_pixmap_async(icon_url, 48, True, item, "server")
                item.setData(Qt.UserRole, guild["id"])
                item.setSizeHint(QSize(60, 60))
                self.servers_list.addItem(item)
        finally:
            self._set_loading(False)

    def _on_friends_loaded(self, friends: list):
        try:
            for friend in friends:
                if friend.get("is_group"):
                    group_name = friend.get("group_name", "Group DM")
                    dm_chan_id = friend.get("dm_channel_id")
                    if not dm_chan_id:
                        continue
                    li = QTreeWidgetItem([group_name])
                    li.setData(0, Qt.UserRole, f"dmchan:{dm_chan_id}")
                    icon_hash = friend.get("icon")
                    if icon_hash:
                        icon_url = f"https://cdn.discordapp.com/channel-icons/{dm_chan_id}/{icon_hash}.png?size=64"
                        self._fetch_pixmap_async(icon_url, 32, True, li, "tree", 0)
                    else:
                        li.setIcon(0, QIcon(self._default_circular_icon(32)))
                    self.channels_tree.addTopLevelItem(li)
                    continue
                if friend.get("type") == 1 and "user" in friend:
                    user = friend["user"]
                    username = user.get("username", "Unknown")
                    avatar = user.get("avatar")
                    uid = user.get("id")
                    li = QTreeWidgetItem([username])
                    if avatar:
                        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png?size=64"
                        self._fetch_pixmap_async(avatar_url, 32, True, li, "tree", 0)
                    else:
                        li.setIcon(0, QIcon(self._default_circular_icon(32)))
                    dm_chan_id = friend.get("dm_channel_id")
                    if dm_chan_id:
                        li.setData(0, Qt.UserRole, f"dmchan:{dm_chan_id}")
                    else:
                        li.setData(0, Qt.UserRole, f"dm:{uid}")
                    self.channels_tree.addTopLevelItem(li)
        finally:
            self._set_loading(False)

    def _on_channels_loaded(self, guild_id: str, channels: list):
        try:
            # Drop stale results if user changed selection
            if self._pending_guild_for_load and str(guild_id) != str(
                self._pending_guild_for_load
            ):
                return
            categories = {c["id"]: c for c in channels if c.get("type") == 4}
            children_by_parent = {}
            for ch in channels:
                if ch.get("type") == 0:
                    pid = ch.get("parent_id")
                    children_by_parent.setdefault(pid, []).append(ch)

            # Add categories as expandable items
            for cat_id, cat in categories.items():
                cat_name = cat.get("name", "Category")
                cat_item = QTreeWidgetItem([cat_name])
                cat_item.setData(0, Qt.UserRole, "category")
                for ch in children_by_parent.get(cat_id, []):
                    name = ch.get("name", "unknown")
                    child = QTreeWidgetItem([f"# {name}"])
                    child.setData(0, Qt.UserRole, ch.get("id"))
                    cat_item.addChild(child)
                # Only add if it has at least one child channel
                if cat_item.childCount() > 0:
                    self.channels_tree.addTopLevelItem(cat_item)

            # Channels without a category: add to top-level
            for ch in children_by_parent.get(None, []):
                name = ch.get("name", "unknown")
                ci = QTreeWidgetItem([f"# {name}"])
                ci.setData(0, Qt.UserRole, ch.get("id"))
                self.channels_tree.addTopLevelItem(ci)
        finally:
            self._set_loading(False)

    def on_tree_item_click(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, str) and data.startswith("dmchan:"):
            # Pre-existing DM channel id, just select it
            chan_id = data.split(":", 1)[1]
            self.selected_channel = chan_id
            self.context_label.setText(item.text(0))
        elif isinstance(data, str) and data.startswith("dm:"):
            user_id = data[3:]
            try:
                dm = self.http.post(
                    "https://discord.com/api/v10/users/@me/channels",
                    json={"recipient_id": user_id},
                    headers=self._headers(),
                    timeout=self._timeout,
                ).json()
                self.selected_channel = dm.get("id")
                self.context_label.setText(f"DM with {item.text(0)}")
            except Exception as e:
                print("Failed to open DM:", e)
        elif isinstance(data, str) and data == "category":
            # Toggle expand/collapse on category click
            item.setExpanded(not item.isExpanded())
            return
        else:
            self.selected_channel = data
            self.context_label.setText(item.text(0))

    def _toggle_reacting(self):
        # Start or stop the background reaction worker
        if not self._reacting:
            emoji_input = self.emoji_edit.text().strip()
            if not self.selected_channel or not emoji_input:
                return
            # Parse multiple emoji tokens (split by comma or whitespace)
            tokens = [t for t in re.split(r"[\s,]+", emoji_input) if t]
            resolved_list = []
            not_found = []
            for t in tokens:
                r = self._resolve_emoji_for_api(t, self.selected_guild_id)
                if r:
                    resolved_list.append(r)
                else:
                    not_found.append(t)
            if not resolved_list:
                self.sig_status.emit(f"No valid emoji found from: {' '.join(tokens)}")
                return
            if not_found:
                self.sig_status.emit(
                    f"Some not found: {', '.join(not_found)}; continuing with others"
                )
            self._reacting = True
            self.react_btn.setText("Stop")
            self.status_label.setText("Starting…")
            order = self.order_combo.currentText()
            oldest_first = self.order_combo.currentIndex() == 1
            clear = self.clear_checkbox.isChecked()
            rate = max(
                1,
                int(
                    getattr(self, "rate_spin", None).value()
                    if hasattr(self, "rate_spin")
                    else 3
                ),
            )
            interval = 1.0 / float(rate)
            page_delay = 0.2
            max_messages = 0
            try:
                if (
                    hasattr(self, "max_messages_spin")
                    and self.max_messages_spin is not None
                ):
                    max_messages = int(self.max_messages_spin.value())
            except Exception:
                max_messages = 0
            channel_id = self.selected_channel
            headers = self._headers()
            emoji_encodings = [urllib.parse.quote(e) for e in resolved_list]

            def worker():
                try:
                    # Use a local session in worker to avoid thread-safety issues
                    sess = requests.Session()
                    sess.headers.update({"User-Agent": USER_AGENT})
                    processed_messages = 0
                    processed_reactions = 0
                    if oldest_first:
                        # Phase 1: find the oldest message id by walking backwards with 'before'
                        oldest_id = None
                        before = None
                        while self._reacting:
                            params = {"limit": 100}
                            if before:
                                params["before"] = before
                            r = sess.get(
                                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                                headers=headers,
                                params=params,
                                timeout=self._timeout,
                            )
                            if r.status_code in (401, 403):
                                self.sig_error.emit(
                                    "Unauthorized"
                                    if r.status_code == 401
                                    else "Forbidden fetching messages"
                                )
                                return
                            if r.status_code == 429:
                                try:
                                    retry = r.json().get("retry_after", 1)
                                except Exception:
                                    retry = 1
                                time.sleep(float(retry) + 0.1)
                                continue
                            msgs = r.json() if r.ok else []
                            if not msgs:
                                break
                            # descending order; last item is the oldest in this page
                            oldest_id = msgs[-1].get("id") or oldest_id
                            before = msgs[-1].get("id")
                            if len(msgs) < 100:
                                break
                            time.sleep(page_delay)

                        if not self._reacting or not oldest_id:
                            return

                        # Phase 2: forward iterate from oldest using 'after'
                        try:
                            start_after = str(int(oldest_id) - 1)
                        except Exception:
                            start_after = oldest_id
                        after = start_after
                        while self._reacting:
                            params = {"limit": 100, "after": after}
                            r = sess.get(
                                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                                headers=headers,
                                params=params,
                                timeout=self._timeout,
                            )
                            if r.status_code in (401, 403):
                                self.sig_error.emit(
                                    "Unauthorized"
                                    if r.status_code == 401
                                    else "Forbidden fetching messages"
                                )
                                return
                            if r.status_code == 429:
                                try:
                                    retry = r.json().get("retry_after", 1)
                                except Exception:
                                    retry = 1
                                time.sleep(float(retry) + 0.1)
                                continue
                            msgs = r.json() if r.ok else []
                            if not msgs:
                                break
                            # Process from oldest to newest within the page
                            msgs.sort(key=lambda m: int(m.get("id", "0")))
                            newest_in_page = msgs[-1].get("id")
                            for m in msgs:
                                if not self._reacting:
                                    break
                                mid = m.get("id")
                                if not mid:
                                    continue
                                # Apply all selected emojis sequentially for this message
                                for emoji_enc in emoji_encodings:
                                    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{mid}/reactions/{emoji_enc}/@me"
                                    t0 = time.monotonic()
                                    resp = (
                                        sess.delete(
                                            url, headers=headers, timeout=self._timeout
                                        )
                                        if clear
                                        else sess.put(
                                            url, headers=headers, timeout=self._timeout
                                        )
                                    )
                                    if resp.status_code in (401, 403):
                                        self.sig_error.emit(
                                            "Unauthorized"
                                            if resp.status_code == 401
                                            else "Forbidden reacting"
                                        )
                                        self.sig_running.emit(False)
                                        return
                                    if resp.status_code == 429:
                                        try:
                                            retry = resp.json().get("retry_after", 1)
                                        except Exception:
                                            retry = 1
                                        time.sleep(float(retry) + 0.1)
                                    else:
                                        # Pace per reaction
                                        elapsed = time.monotonic() - t0
                                        if elapsed < interval:
                                            time.sleep(interval - elapsed)
                                    processed_reactions += 1
                                    self.sig_status.emit(
                                        f"Msgs {processed_messages} | Reactions {processed_reactions}…"
                                    )
                                processed_messages += 1
                                if max_messages and processed_messages >= max_messages:
                                    self.sig_status.emit(
                                        f"Msgs {processed_messages} | Reactions {processed_reactions} (limit reached)"
                                    )
                                    self.sig_running.emit(False)
                                    return
                            after = newest_in_page
                            time.sleep(page_delay)
                    else:
                        # Newest → Oldest using `before` pagination
                        before = None
                        while self._reacting:
                            params = {"limit": 100}
                            if before:
                                params["before"] = before
                            r = sess.get(
                                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                                headers=headers,
                                params=params,
                                timeout=self._timeout,
                            )
                            if r.status_code in (401, 403):
                                self.sig_error.emit(
                                    "Unauthorized"
                                    if r.status_code == 401
                                    else "Forbidden fetching messages"
                                )
                                return
                            if r.status_code == 429:
                                try:
                                    retry = r.json().get("retry_after", 1)
                                except Exception:
                                    retry = 1
                                time.sleep(float(retry) + 0.1)
                                continue
                            msgs = r.json() if r.ok else []
                            if not msgs:
                                break
                            # API returns newest first; process in that order
                            for m in msgs:
                                if not self._reacting:
                                    break
                                mid = m.get("id")
                                if not mid:
                                    continue
                                # Apply all selected emojis sequentially for this message
                                for emoji_enc in emoji_encodings:
                                    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{mid}/reactions/{emoji_enc}/@me"
                                    t0 = time.monotonic()
                                    resp = (
                                        sess.delete(
                                            url, headers=headers, timeout=self._timeout
                                        )
                                        if clear
                                        else sess.put(
                                            url, headers=headers, timeout=self._timeout
                                        )
                                    )
                                    if resp.status_code in (401, 403):
                                        self.sig_error.emit(
                                            "Unauthorized"
                                            if resp.status_code == 401
                                            else "Forbidden reacting"
                                        )
                                        self.sig_running.emit(False)
                                        return
                                    if resp.status_code == 429:
                                        try:
                                            retry = resp.json().get("retry_after", 1)
                                        except Exception:
                                            retry = 1
                                        time.sleep(float(retry) + 0.1)
                                    else:
                                        elapsed = time.monotonic() - t0
                                        if elapsed < interval:
                                            time.sleep(interval - elapsed)
                                    processed_reactions += 1
                                    self.sig_status.emit(
                                        f"Msgs {processed_messages} | Reactions {processed_reactions}…"
                                    )
                                processed_messages += 1
                                if max_messages and processed_messages >= max_messages:
                                    self.sig_status.emit(
                                        f"Msgs {processed_messages} | Reactions {processed_reactions} (limit reached)"
                                    )
                                    self.sig_running.emit(False)
                                    return
                            before = msgs[-1].get("id")
                            time.sleep(page_delay)
                except Exception as e:
                    print("React worker error:", e)
                finally:
                    # Marshal UI updates to main thread
                    self.sig_running.emit(False)
                    self.sig_status.emit("Idle")

            t = threading.Thread(target=worker, daemon=True)
            t.start()
        else:
            # Stop
            self._reacting = False
            self.react_btn.setChecked(False)
            self.react_btn.setText("Start")
            self.status_label.setText("Stopping…")

    def _open_token_help(self):
        """Open the GitHub HOW_TO_GET_TOKEN.md guide in the user's default browser."""
        try:
            QDesktopServices.openUrl(
                QUrl(
                    "https://github.com/Otm02/DiscordEmotifyV2/blob/main/HOW_TO_GET_TOKEN.md"
                )
            )
        except Exception:
            self.sig_status.emit("Could not open help URL")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set application icon for taskbar and new windows
    try:
        app_icon_path = resource_path("DiscordEmotify.ico")
        if os.path.exists(app_icon_path):
            app.setWindowIcon(QIcon(app_icon_path))
    except Exception:
        pass
    w = DiscordEmotify()
    w.show()
    sys.exit(app.exec_())
