# claude-limits

Your Claude usage limits in the GNOME top bar.

    ✳ 57% · 15%

Left number is the 5-hour session window, right is the weekly one. Click for
reset countdowns and a per-surface breakdown.

Built because the GNOME Extensions store version stopped loading on GNOME 50
(it declares `shell-version` up to 49). This is not a shell extension — it is a
StatusNotifierItem, which the AppIndicator extension picks up live, so it
appears the moment you start it. **No shell restart, no logout** — which matters
on Wayland, where a running shell cannot load a newly added extension directory
and there is no way to restart the shell in place.

## Install

Needs GNOME with the AppIndicator extension enabled (default on Ubuntu).

    sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1   # usually already present
    git clone https://github.com/Lawrecesss/claude-limits
    cd claude-limits
    ./install.sh

That installs a systemd user service and starts it. To run it once without
installing:

    /usr/bin/python3 claude-limits-tray.py

Use `/usr/bin/python3` explicitly — a virtualenv on your `PATH` will not have
PyGObject.

## The menu

- **Session (5h)** — percentage and time until reset
- **Weekly** — same, for the rolling 7-day window
- **Weekly (Opus)** — only when the API reports a separate Opus window
- **Weekly breakdown** — Claude Code / Chats / Cowork / Other
- **Refresh now** (shows the last update time), **Open usage page**, **Quit**

Polls every 5 minutes. Countdowns tick every minute without re-polling.

## Configuration

Environment variables, read at startup:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CLAUDE_LIMITS_INTERVAL` | `300` | Seconds between polls |
| `CLAUDE_LIMITS_YELLOW` | `50` | Percent at which the icon turns yellow |
| `CLAUDE_LIMITS_ORANGE` | `70` | Percent at which it turns orange |
| `CLAUDE_LIMITS_RED` | `90` | Percent at which it turns red |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Where to find `.credentials.json` |

Set them in the unit with `systemctl --user edit claude-limits.service`.

## How it gets the data

Reads the OAuth access token Claude Code stores in
`$CLAUDE_CONFIG_DIR/.credentials.json` and calls:

    GET https://api.anthropic.com/api/oauth/usage
    Authorization: Bearer <token>
    anthropic-beta: oauth-2025-04-20

This endpoint is undocumented — it is what Claude Code's own `/usage` uses, so
it may change without warning. The token is re-read on every poll, so a token
Claude Code refreshed is picked up without a restart. Nothing is sent anywhere
but `api.anthropic.com`.

The token is not refreshed here. If it expires the label shows `re-auth`; run
`claude` once and the next poll recovers.

## Icons

The mark changes colour with whichever window is further along:

| Usage | Icon |
| --- | --- |
| below 50% | white |
| 50–70% | yellow |
| 70–90% | orange |
| 90–100%, and on errors | red |

`icons/claude.png` is the source of truth. `make-icons.py` derives the three
tinted variants from it by recolouring opaque pixels, keeping per-pixel alpha so
the edges stay smooth. The icon is the only pressure cue a tray item has — its
label is plain text and cannot be coloured.

To restyle, replace `icons/claude.png` or edit `TINTS`, then:

    /usr/bin/python3 -I make-icons.py
    systemctl --user restart claude-limits.service

To keep the mark white at all times, set every `TINTS` entry to
`(255, 255, 255)`.

Icons are referenced by absolute path; the AppIndicator extension treats an icon
name starting with `/` as a file, so nothing is installed into an icon theme.
If a file goes missing it falls back to `utilities-system-monitor-symbolic`.

## Troubleshooting

    systemctl --user status claude-limits.service
    journalctl --user -u claude-limits.service -f

No icon at all? Check the AppIndicator extension is on:

    gnome-extensions enable ubuntu-appindicators@ubuntu.com

## Notes

Not affiliated with Anthropic. The Claude mark in `icons/` is Anthropic's
trademark and is used here only to label their own service.

MIT licensed.
