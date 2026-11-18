"""Adds Chintan's Android pieces to the project that `flutter create` generates.

Run from the app/ folder after `flutter create`:
    python3 tool/patch_android.py
It is safe to run more than once.
"""
import pathlib
import re
import shutil

APP = pathlib.Path(__file__).resolve().parent.parent
PKG_DIR = APP / "android/app/src/main/kotlin/com/chintanai/chintan_assistant"
MANIFEST = APP / "android/app/src/main/AndroidManifest.xml"

# 1. Kotlin: our MainActivity (method channel) and the call-screening service.
PKG_DIR.mkdir(parents=True, exist_ok=True)
for name in ("MainActivity.kt", "ChintanScreeningService.kt"):
    shutil.copy(APP / "android_overlay" / name, PKG_DIR / name)

# 2. Manifest: permissions, app name, the service, and link/phone/WhatsApp queries.
m = MANIFEST.read_text()
perms = ["android.permission.INTERNET", "android.permission.READ_CONTACTS", "android.permission.POST_NOTIFICATIONS"]
for p in perms:
    if p not in m:
        m = m.replace("<application", f'<uses-permission android:name="{p}"/>\n    <application', 1)
m = re.sub(r'android:label="[^"]*"', 'android:label="Chintan"', m, count=1)
service = """
        <service
            android:name=".ChintanScreeningService"
            android:permission="android.permission.BIND_SCREENING_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.telecom.CallScreeningService"/>
            </intent-filter>
        </service>
"""
if "ChintanScreeningService" not in m:
    m = m.replace("</application>", service + "    </application>", 1)
queries = """
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="https"/></intent>
        <intent><action android:name="android.intent.action.DIAL"/><data android:scheme="tel"/></intent>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="tel"/></intent>
"""
if "<queries>" in m:
    if 'android:scheme="tel"' not in m:
        m = m.replace("<queries>", "<queries>" + queries, 1)
else:
    m = m.replace("</manifest>", f"    <queries>{queries}    </queries>\n</manifest>", 1)
MANIFEST.write_text(m)

# 3. Android 10+ (call screening needs it).
for gradle in (APP / "android/app/build.gradle.kts", APP / "android/app/build.gradle"):
    if gradle.exists():
        g = gradle.read_text()
        g = re.sub(r"minSdk\s*=\s*flutter\.minSdkVersion", "minSdk = 29", g)
        g = re.sub(r"minSdkVersion\s+flutter\.minSdkVersion", "minSdkVersion 29", g)
        gradle.write_text(g)

print("Android project patched for Chintan.")
