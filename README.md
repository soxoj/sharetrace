<div align="center">

<h1>ShareTrace</h1>

### 🎭 Reveal the identity behind a share link

**A fork of [soxoj/sharetrace](https://github.com/soxoj/sharetrace) with Google Docs and GitHub owner-email extraction added.**

<br>

<img src="assets/capture.png" width="600" alt="ShareTrace CLI capture" />

<br><br>

<!-- Feature badges -->
<p>
  <a href="https://github.com/7onez/sharetrace"><img src="https://img.shields.io/badge/version-fork-0080ff?style=for-the-badge&logo=git&logoColor=white" alt="Fork"></a>&nbsp;
  <a href="https://github.com/soxoj/sharetrace"><img src="https://img.shields.io/badge/upstream-soxoj%2Fsharetrace-0080ff?style=for-the-badge&logo=github&logoColor=white" alt="Upstream soxoj/sharetrace"></a>&nbsp;
  <a href="#supported-sources"><img src="https://img.shields.io/badge/sources-13-ff6d00?style=for-the-badge&logo=searchengin&logoColor=white" alt="13 sources"></a>&nbsp;
  <a href="#installation"><img src="https://img.shields.io/badge/API_keys-none-00bfa5?style=for-the-badge&logo=shield&logoColor=white" alt="No API keys"></a>
</p>

<!-- GitHub stats -->
<p>
  <a href="https://github.com/7onez/sharetrace/stargazers"><img src="https://img.shields.io/github/stars/7onez/sharetrace?style=flat-square&logo=github&label=Stars" alt="Stars"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace/network/members"><img src="https://img.shields.io/github/forks/7onez/sharetrace?style=flat-square&logo=github&label=Forks" alt="Forks"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace/issues"><img src="https://img.shields.io/github/issues/7onez/sharetrace?style=flat-square&logo=github&label=Issues" alt="Issues"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace/pulls"><img src="https://img.shields.io/github/issues-pr/7onez/sharetrace?style=flat-square&logo=github&label=PRs" alt="PRs"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace/commits"><img src="https://img.shields.io/github/last-commit/7onez/sharetrace?style=flat-square&logo=github&label=Last%20Commit" alt="Last Commit"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace"><img src="https://img.shields.io/github/repo-size/7onez/sharetrace?style=flat-square&logo=github&label=Size" alt="Repo Size"></a>&nbsp;
  <a href="https://github.com/7onez/sharetrace/graphs/contributors"><img src="https://img.shields.io/github/contributors/7onez/sharetrace?style=flat-square&logo=github&label=Contributors" alt="Contributors"></a>
</p>

<sub>Fork maintained by <a href="https://www.linkedin.com/in/hieu-minh-ngo-hieupc/"><b>Hieu Ngo</b></a> &bull; <a href="mailto:hieu.ngo@chongluadao.vn">hieu.ngo@chongluadao.vn</a> &bull; <a href="https://chongluadao.vn">chongluadao.vn</a></sub>

</div>

<br>

---

<br>

## 🌟 What's new in this fork

All upstream functionality preserved. Additions over [soxoj/sharetrace](https://github.com/soxoj/sharetrace):

| Addition | Covers | Notes |
|----------|--------|-------|
| **Google Docs source** (`gdoc`) | Docs, Sheets, Slides, Drawings, Forms, Drive files, Apps Script, Jamboard, My Maps | Owner email + Google ID + creation/modification dates from the public Drive `v2beta` metadata endpoint. API key overridable via `SHARETRACE_GDOC_API_KEY`. Clean-room rewrite against the endpoint first documented by [Malfrats/xeuledoc](https://github.com/Malfrats/xeuledoc) |
| **GitHub source** (`github`) | Commit URLs, PR-commit URLs, profile URLs | Commit: parses `.patch` mbox `From:` header with RFC 5322 parser (handles quoted display names). Profile: scans recent public PushEvents (last 90 days). `users.noreply.github.com` emails flagged via `is_noreply` |
| **28 new tests** | Router + `gdoc` + `github` modules | Mocked unit tests + live-verified against real public documents and commits |

<br>

## 💻 Quick start

```bash
python -m sharetrace <url>
```

### Advanced

```bash
# JSON output (scriptable)
python -m sharetrace <url> --json

# List all supported sources
python -m sharetrace --list

# Override the default Google Drive API key (if it gets revoked)
SHARETRACE_GDOC_API_KEY=<your-key> python -m sharetrace <drive-url>
```

<br>

## ⚙️ Installation

```bash
git clone https://github.com/7onez/sharetrace.git
cd sharetrace
pip install -r requirements.txt
```

<br>

## 📖 Usage examples

```bash
# Google Docs / Sheets / Drive — extracts owner email + Google ID + dates
python -m sharetrace "https://docs.google.com/document/d/<id>/edit" --json

# GitHub commit — extracts committer name + email
python -m sharetrace "https://github.com/<user>/<repo>/commit/<sha>"

# GitHub profile — scans recent public PushEvents for emails
python -m sharetrace "https://github.com/<username>"

# TikTok share link — extracts sharer identity + device + share method
python -m sharetrace "https://vm.tiktok.com/<code>"

# ChatGPT share — extracts display name
python -m sharetrace "https://chatgpt.com/share/<uuid>"
```

<br>

## 🔎 Supported sources

| Name                | Extracts | Notes |
| ------------------- | -------- | ----- |
| [TikTok](https://tiktok.com)              | User ID, Username, Nickname, Country, Avatar, Signature, Device, Share Method, Timestamp, Follower/Following/Video/Heart Counts, Private Account, DM Available | Requires short share link (`vm.tiktok.com` / `vt.tiktok.com`) |
| [Instagram](https://instagram.com)        | Username, User ID, Display Name, Profile URL, Profile Pic | Sharer data might expire within a few days; only fresh share links contain identity info |
| [Discord](https://discord.com)            | User ID, Username, Display Name, Avatar, Creation Time | Vanity invites may not contain inviter data |
| [ChatGPT](https://chatgpt.com)            | Display Name | |
| [Claude](https://claude.ai)               | Display Name, User ID | |
| [Perplexity](https://perplexity.ai)       | Username, Avatar, User ID | |
| [Microsoft](https://sharepoint.com)       | Email | From SharePoint/OneDrive personal links; no HTTP request needed |
| [Pinterest](https://pinterest.com)        | Username, User ID, Display Name, Avatar, Profile URL | Requires short share link (`pin.it`) with invite code |
| [Substack](https://substack.com)          | User ID, Name, Handle, Bio, Avatar, Profile Setup Date | Requires referral share link (`?r=` parameter) |
| [Suno](https://suno.com)                  | Username, Display Name, Avatar, Profile URL | |
| [Telegram](https://telegram.org)          | User ID | Decoded from joinchat link hash; no HTTP request needed. Links starting with `AAAAA` decode to user_id=0 and contain no useful data |
| **[Google Docs](https://docs.google.com)** ★ | Owner Email, Name, Google ID, Avatar, Creation Date, Last Edit, Public Permissions | Works for Docs, Sheets, Slides, Drawings, Forms, Drive files, Apps Script, Jamboard, My Maps. Requires document to be publicly shared. API key overridable via `SHARETRACE_GDOC_API_KEY` |
| **[GitHub](https://github.com)** ★        | Email, Name, Commit SHA, Repo (commit URL); Username, Emails list (profile URL) | Commit URL: parses `.patch` mbox `From:` header. Profile URL: scans recent public PushEvents (last 90 days). `users.noreply.github.com` emails flagged. Profile route subject to GitHub's 60/hr unauth rate limit |

★ = added in this fork

<br>

## 🌐 Web interface (community)

A self-hosted Flask wrapper with a browser UI is available: [voelspriet/sharetrace-web](https://github.com/voelspriet/sharetrace-web) — live demo at <https://share.whopostedwhat.com>. Maintained separately against upstream; all extraction logic still lives in this repo.

<p align="center">
  <img width="700" alt="Screenshot of share.whopostedwhat.com" src="https://github.com/user-attachments/assets/54d5ee25-0a73-457b-aa8b-4bf7a6a90c24" />
</p>

<br>

## 😊 SOWEL classification

This tool uses the following OSINT techniques:

- [SOTL-1.4. Analyze Internal Identifiers](https://sowel.soxoj.com/internal-identifiers)
- [SOTL-3.1. Extract Metadata From User-Generated Content](https://sowel.soxoj.com/Techniques/SOTL-3.1.+Extract+Metadata+From+User-Generated+Content)

<br>

## 🙏 Acknowledgements

- **[soxoj/sharetrace](https://github.com/soxoj/sharetrace)** — the original project this fork builds on. The CLI scaffolding, platform routing, and every source module for **TikTok, Instagram, Discord, ChatGPT, Claude, Perplexity, Microsoft/SharePoint, Pinterest, Substack, Suno, and Telegram** were built by [soxoj](https://github.com/soxoj) and upstream contributors. All credit for the core project belongs to them.
- **[Malfrats/xeuledoc](https://github.com/Malfrats/xeuledoc)** — the Google Drive `v2beta` owner-metadata endpoint was first documented here (GPLv3). The `gdoc` module in this fork is a clean-room rewrite against the same public API.
- **[avonture.be](https://www.avonture.be/blog/github-retrieve-email/)** — documented the GitHub `.patch` trick that the `github` module's commit route relies on.

<br>

## ⚠️ Ethical use & disclaimer

This tool is created for **educational and defensive purposes only**.

- Only analyze links that have been publicly shared or sent to you.
- Only hit endpoints that are explicitly public (no auth, no scraping of private data).
- The fork maintainer is not responsible for misuse.

Permitted: journalistic fact-checking, corporate security research, authorized penetration testing, counter-scam / anti-fraud work (the reason this fork exists), personal reputation monitoring.

Forbidden: doxxing, harassment, stalking, unauthorized surveillance, social engineering for fraud, privacy invasion, any criminal activity.

<br>

---

<br>

<div align="center">
<sub>
Fork by <a href="https://www.linkedin.com/in/hieu-minh-ngo-hieupc/"><b>Hieu Ngo</b></a>
&bull;
<a href="mailto:hieu.ngo@chongluadao.vn">hieu.ngo@chongluadao.vn</a>
&bull;
<a href="https://chongluadao.vn">chongluadao.vn</a>
&bull;
Upstream: <a href="https://github.com/soxoj/sharetrace"><b>soxoj/sharetrace</b></a>
&bull;
License: <a href="https://github.com/soxoj/sharetrace/blob/main/LICENSE">GPL-3.0</a>
</sub>
</div>
