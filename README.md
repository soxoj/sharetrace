<h1 align="center">ShareTrace</h1>
<p align="center">🎭 Reveal the identity behind a share link</p>
<p align="center">
  <img src="assets/capture.png" />
</p>


## 💻 Quick Start

```bash
python -m sharetrace <url>
```

## 📚 Advanced usage:
```bash
# Output as JSON for piping
python -m sharetrace <url> --json

# List all supported platforms
python -m sharetrace --list
```

## ⚙️ Installation

```bash
git clone https://github.com/loaded/sharetrace.git
cd sharetrace
pip install -r requirements.txt
```

## Supported sources

| Name                | Extracts | Notes |
| ------------------- | -------- | ----- |
| [TikTok](https://tiktok.com)              | User ID, Username, Nickname, Country, Avatar, Signature, Device, Share Method, Timestamp, Follower/Following/Video/Heart Counts, Private Account, DM Available | Requires short share link (`vm.tiktok.com` / `vt.tiktok.com`) |
| [Instagram](https://instagram.com)        | Username, User ID, Display Name, Profile URL, Profile Pic | Sharer data expires within ~24 hours; only fresh share links contain identity info |
| [Discord](https://discord.com)            | User ID, Username, Display Name, Avatar, Creation Time | Vanity invites may not contain inviter data |
| [ChatGPT](https://chatgpt.com)            | Display Name | |
| [Claude](https://claude.ai)               | Display Name, User ID | |
| [Perplexity](https://perplexity.ai)       | Username, Avatar, User ID | |
| [Microsoft](https://sharepoint.com)       | Email | From SharePoint/OneDrive personal links; no HTTP request needed |
| [Pinterest](https://pinterest.com)        | Username, User ID, Display Name, Avatar, Profile URL | Requires short share link (`pin.it`) with invite code |
| [Substack](https://substack.com)          | User ID, Name, Handle, Bio, Avatar, Profile Setup Date | Requires referral share link (`?r=` parameter) |
| [Suno](https://suno.com)                  | Username, Display Name, Avatar, Profile URL | |
| [Telegram](https://telegram.org)          | User ID | Decoded from joinchat link hash; no HTTP request needed. Links starting with `AAAAA` decode to user_id=0 and contain no useful data |

## 😊 SOWEL classification
This tool uses the following OSINT techniques:
- [SOTL-1.4. Analyze Internal Identifiers](https://sowel.soxoj.com/internal-identifiers)
- [SOTL-3.1. Extract Metadata From User-Generated Content](https://sowel.soxoj.com/Techniques/SOTL-3.1.+Extract+Metadata+From+User-Generated+Content)

## ⚠️ Ethical Use & Disclaimer

This tool is created for **educational and defensive purposes only**.
- Only analyze links that have been publicly shared or sent to you.
- I am not responsible for any misuse of this tool.