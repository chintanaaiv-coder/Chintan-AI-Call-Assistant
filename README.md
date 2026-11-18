# Chintan AI Call Assistant

An AI call assistant for a Chartered Accountant's practice. Chintan answers calls,
finds out who is calling and why, and hands every decision back to you. It never
blocks or decides on its own.

| Folder | What it is |
| --- | --- |
| `server/` | The brain: answers forwarded calls (Exotel), talks in your cloned voice (ElevenLabs), applies the CA rules (Gemini or Claude), saves transcripts and recordings. |
| `app/` | The Flutter app for Android and iPhone: call log, live call screen, recordings, WhatsApp, snooze, settings. |
| `chintan-call-assistant.html` | The original web mockup, kept for reference. |

## Get the Android app

Every change to `app/` builds a new APK automatically. Download the latest from
**Releases -> "Chintan AI Call Assistant (latest Android build)"** on your phone and
tap the `.apk` to install (allow "install unknown apps" for your browser once).

## What it does

- Screens calls (all calls, or only unknown numbers) and shows a live transcript.
- Sorts calls into CA categories: regulatory/notice, client deadline, bank/DSA, scam risk, sales and more.
  Regulatory and scam calls always go to the top. Deadlines (44AB, GSTR-3B, TDS...) are worked out in code.
- Safety rules the AI can never break: no OTPs, PINs, PAN, Aadhaar, figures or client data to anyone;
  a firm no to client-database requests; tax-officer/bank claims are only recorded for you to verify.
- During a call: send a line for Chintan to say (quick replies or typed, said word for word), Join, or Wrap up.
- After a call: summary, recording (both voices), transcript, Call back, WhatsApp (you edit the draft first), Mute caller.
- Snooze with auto-resume.
- A **Test a call** button: type what a caller says and watch Chintan respond, no phone needed.

Setup: see [docs/SETUP.md](docs/SETUP.md).
