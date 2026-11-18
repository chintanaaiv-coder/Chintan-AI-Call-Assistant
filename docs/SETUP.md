# Setting up Chintan

Four parts, in this order. You can stop after step 2 and already test everything by typing.

## 1. Accounts and keys you need

| What | Where | Used for |
| --- | --- | --- |
| Gemini API key | aistudio.google.com (the same key as the web mockup) | Everything: the AI brain, understanding the caller and speaking. Free tier to start. |
| ElevenLabs (optional, later) | elevenlabs.io, paid Starter plan | Only if you want Chintan to speak in your own cloned voice: set `SPEECH_PROVIDER=elevenlabs`. |
| Exotel account + a virtual number | exotel.com | The phone number calls are forwarded to |
| Render account | render.com | Runs the server 24/7 (about $7/month for the plan with storage) |

## 2. Put the server online (Render)

1. On render.com: **New -> Blueprint**, pick the `Chintan-AI-Call-Assistant` repo. It reads `render.yaml`.
2. Fill in `GEMINI_API_KEY` when asked. That's the only key you need.
   `APP_TOKEN` and `EXOTEL_STREAM_SECRET` are generated for you: open the service's
   **Environment** tab to copy them.
3. When it's live, open `https://<your-service>.onrender.com/health`. `problems` lists anything still missing.

**Try it now:** install the app, Settings -> paste the server address and `APP_TOKEN` -> Save and connect.
Then tap the flask icon (Test a call) and type what a caller would say.

> **Privacy:** on Gemini's free tier Google may use the data to improve its products; on the paid tier it
> doesn't. Fine for testing; switch the key's project to paid billing before real client calls.

### Teach Chintan how you talk

App -> the speaking-head icon -> **Add a call**. Paste transcripts of your real calls (iPhone: record the call,
then Notes -> Call Recordings -> transcript -> copy). Chintan reads a few similar ones before each reply and copies
your tone and Hindi/English mix. Numbers, PAN, Aadhaar, amounts and emails are blanked out automatically; remove
client names yourself. Start with 3-5 typical calls.

## 3. Connect the phone number (Exotel)

In Exotel, create a call flow (App Bazaar -> Create) for your Exotel number:

1. **Voicebot** applet. URL: `wss://<your-service>.onrender.com/exotel/stream/<EXOTEL_STREAM_SECRET>`
2. **Passthru** applet right after it. URL: `https://<your-service>.onrender.com/exotel/after-stream/<EXOTEL_STREAM_SECRET>`
   - If it answers **200** -> **Connect** applet to your own mobile number (this is the "Join call" button).
   - Otherwise -> **Hangup**.

Test by calling your Exotel number from another phone: Chintan should greet you, and the call appears live in the app.

> Check with Exotel when you sign up: (a) that your number accepts calls forwarded from your mobile, and
> (b) how their Passthru applet branches (on HTTP 200 vs other). The server sends 200 to connect and 302 to hang up.

## 4. Send your calls to Chintan

**Android:** in the app, Settings -> *Call screening on this phone* -> **Allow**. Pick which calls go to Chintan.
Then under *Call forwarding*, enter your Exotel number and tap **When busy / declined** (and the others if you like),
pressing call each time. Chintan declines the calls it should handle; your network forwards them to the Exotel number.

**iPhone:** set up the same forwarding codes in the Phone app (dial them). iPhones do not let apps screen calls,
so a call goes to Chintan when you decline it. The app works the same for the live screen, recordings and so on.

To undo all forwarding: dial `##002#`.

## Building the app yourself (optional)

GitHub builds the APK for you. To build on a computer with Flutter installed:

```
cd app
flutter create --org com.chintanai --project-name chintan_assistant --platforms android,ios .
python3 tool/patch_android.py
flutter pub get && dart run flutter_launcher_icons
flutter build apk --release        # Android
# iPhone: open ios/Runner.xcworkspace in Xcode on a Mac (Apple Developer account needed)
```

## Running the server on your laptop (optional)

```
cd server
pip install -r requirements-dev.txt
cp .env.example .env   # fill in the keys
export $(grep -v '^#' .env | xargs) && uvicorn chintan.main:app --reload
python -m pytest -q    # tests, with CHINTAN_NO_AUTOAPP=1
```

## Costs to expect (rough)

Every screened call uses Exotel minutes, speech recognition, the AI and the voice. A 1-minute call is roughly a few
rupees in total. Check each provider's current pricing.
