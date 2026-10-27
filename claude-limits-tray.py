#!/usr/bin/python3
"""Claude usage limits in the GNOME top bar, via StatusNotifierItem.

Appears immediately in a running shell (the appindicator extension picks up new
tray items live), so it needs no shell restart and no logout.
"""

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import GLib, Gio, Gtk  # noqa: E402

API_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"
USAGE_PAGE = "https://claude.ai/settings/usage"
APP_ID = "claude-limits"

# The appindicator extension treats an icon name starting with "/" as a file
# path, so these are used directly — no icon-theme install needed.
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
ICON_OK = os.path.join(ICON_DIR, "claude.png")
ICON_WARN = os.path.join(ICON_DIR, "claude-warn.png")
ICON_CRIT = os.path.join(ICON_DIR, "claude-crit.png")
# Falls back to a stock icon if the drawn ones ever go missing.
ICON_FALLBACK = "utilities-system-monitor-symbolic"


def icon_for(percent):
    if percent >= CRIT_AT:
        path = ICON_CRIT
    elif percent >= WARN_AT:
        path = ICON_WARN
    else:
        path = ICON_OK
    return path if os.path.exists(path) else ICON_FALLBACK

REFRESH_SECONDS = int(os.environ.get("CLAUDE_LIMITS_INTERVAL", "300"))
WARN_AT = int(os.environ.get("CLAUDE_LIMITS_WARN", "75"))
CRIT_AT = int(os.environ.get("CLAUDE_LIMITS_CRIT", "90"))


def credentials_path():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(base, ".credentials.json")


def read_token():
    """Re-read on every poll so a token Claude Code refreshed is picked up."""
    with open(credentials_path(), encoding="utf-8") as fh:
        data = json.load(fh)
    oauth = data.get("claudeAiOauth") or {}
    return oauth.get("accessToken") or data.get("accessToken")


def fetch_usage(token):
    req = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": OAUTH_BETA,
            "Content-Type": "application/json",
            "User-Agent": "claude-limits-tray/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def format_reset(iso):
    if not iso:
        return "reset time unknown"
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return "reset time unknown"
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    minutes = round((when - datetime.now(timezone.utc)).total_seconds() / 60)
    if minutes <= 0:
        return "resets any moment"
    if minutes < 60:
        return f"resets in {minutes}m"

    local = when.astimezone()
    if minutes < 24 * 60:
        return f"resets in {minutes // 60}h {minutes % 60}m ({local:%H:%M})"
    return f"resets in {minutes // (24 * 60)}d ({local:%a %H:%M})"


class ClaudeLimitsTray:
    def __init__(self):
        self.indicator = AppIndicator.Indicator.new(
            APP_ID, icon_for(0), AppIndicator.IndicatorCategory.SYSTEM_SERVICES
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Claude limits")
        # The guide keeps the panel width stable as the digits change.
        self.indicator.set_label("…", "100% · 100%")

        self.rows = {}
        self.indicator.set_menu(self._build_menu())

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._on_timer)
        # Keep the countdowns honest without re-hitting the API.
        GLib.timeout_add_seconds(60, self._on_tick)
        self.last_data = None

    def _build_menu(self):
        menu = Gtk.Menu()

        for key, text in (
            ("session", "Session (5h): …"),
            ("weekly", "Weekly: …"),
            ("opus", "Weekly (Opus): …"),
        ):
            item = Gtk.MenuItem(label=text)
            item.set_sensitive(False)
            menu.append(item)
            self.rows[key] = item
        self.rows["opus"].set_visible(False)

        self.breakdown_sep = Gtk.SeparatorMenuItem()
        menu.append(self.breakdown_sep)
        self.breakdown_items = []
        for _ in range(4):
            item = Gtk.MenuItem(label="")
            item.set_sensitive(False)
            item.set_visible(False)
            menu.append(item)
            self.breakdown_items.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        self.refresh_item = Gtk.MenuItem(label="Refresh now")
        self.refresh_item.connect("activate", lambda _i: self.refresh())
        menu.append(self.refresh_item)

        open_item = Gtk.MenuItem(label="Open usage page")
        open_item.connect(
            "activate",
            lambda _i: Gio.AppInfo.launch_default_for_uri(USAGE_PAGE, None),
        )
        menu.append(open_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _i: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        self.rows["opus"].set_visible(False)
        for item in self.breakdown_items:
            item.set_visible(False)
        return menu

    def _on_timer(self):
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def _on_tick(self):
        if self.last_data:
            self._render(self.last_data)
        return GLib.SOURCE_CONTINUE

    def refresh(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            token = read_token()
        except OSError as exc:
            GLib.idle_add(self._show_error, "no creds", str(exc))
            return
        except ValueError as exc:
            GLib.idle_add(self._show_error, "bad creds", str(exc))
            return
        if not token:
            GLib.idle_add(
                self._show_error, "no token", "No OAuth token — run `claude` and sign in"
            )
            return

        try:
            data = fetch_usage(token)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                GLib.idle_add(
                    self._show_error, "re-auth", "Token rejected — run `claude` to refresh it"
                )
            else:
                GLib.idle_add(self._show_error, "err", f"API returned HTTP {exc.code}")
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            GLib.idle_add(self._show_error, "offline", f"Network error: {exc}")
            return
        except ValueError as exc:
            GLib.idle_add(self._show_error, "err", f"Bad response: {exc}")
            return

        GLib.idle_add(self._accept, data)

    def _accept(self, data):
        self.last_data = data
        self._render(data)
        return GLib.SOURCE_REMOVE

    def _show_error(self, short, detail):
        self.indicator.set_label(short, "100% · 100%")
        self.indicator.set_icon_full(icon_for(100), "Claude limits unavailable")
        self.rows["session"].set_label(detail)
        self.rows["weekly"].set_label("")
        self.rows["opus"].set_visible(False)
        self.breakdown_sep.set_visible(False)
        for item in self.breakdown_items:
            item.set_visible(False)
        self.refresh_item.set_label("Retry now")
        print(f"claude-limits: {detail}", flush=True)
        return GLib.SOURCE_REMOVE

    def _render(self, data):
        session = data.get("five_hour") or {}
        weekly = data.get("seven_day") or {}
        opus = data.get("seven_day_opus") or {}

        s_pct = round(session.get("utilization") or 0)
        w_pct = round(weekly.get("utilization") or 0)

        self.indicator.set_label(f"{s_pct}% · {w_pct}%", "100% · 100%")
        worst = max(s_pct, w_pct)
        self.indicator.set_icon_full(
            icon_for(worst), f"Claude: session {s_pct}%, weekly {w_pct}%"
        )

        flag = " ⚠" if worst >= WARN_AT else ""
        self.rows["session"].set_label(
            f"Session (5h): {s_pct}% — {format_reset(session.get('resets_at'))}{flag}"
        )
        self.rows["weekly"].set_label(
            f"Weekly: {w_pct}% — {format_reset(weekly.get('resets_at'))}"
        )

        if opus:
            o_pct = round(opus.get("utilization") or 0)
            self.rows["opus"].set_label(
                f"Weekly (Opus): {o_pct}% — {format_reset(opus.get('resets_at'))}"
            )
            self.rows["opus"].set_visible(True)
        else:
            self.rows["opus"].set_visible(False)

        rows = ((data.get("seven_day_breakdown") or {}).get("rows")) or []
        shown = [r for r in rows if (r.get("percent") or 0) > 0]
        self.breakdown_sep.set_visible(bool(shown))
        for item, row in zip(self.breakdown_items, shown):
            item.set_label(
                f"   {row.get('display_name') or row.get('key')}: {round(row['percent'])}%"
            )
            item.set_visible(True)
        for item in self.breakdown_items[len(shown):]:
            item.set_visible(False)

        self.refresh_item.set_label(f"Refresh now  ·  updated {datetime.now():%H:%M}")
        return GLib.SOURCE_REMOVE


def main():
    ClaudeLimitsTray()
    Gtk.main()


if __name__ == "__main__":
    main()
