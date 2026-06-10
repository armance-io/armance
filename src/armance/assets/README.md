# Armance icon assets

Bundled launcher / desktop-shortcut icons. Shipped in the wheel and read by
`armance.service.shortcuts` when generating a desktop shortcut.

| File | Used by |
|---|---|
| `icon.png` | Linux `.desktop` entry |
| `icon.ico` | Windows `.lnk` (add when available) |
| `icon.icns` | macOS `.app` (add when available) |

> `icon.png` is currently a **placeholder** (a small solid square). Replace it
> with the real brand mark (the Armance hat 👒) — and add `icon.ico` /
> `icon.icns` for full per-OS fidelity. Shortcut generation degrades
> gracefully when an asset is missing (no icon, no crash).
