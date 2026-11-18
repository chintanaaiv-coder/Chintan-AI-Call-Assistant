import 'dart:io' show Platform;

import 'package:flutter/services.dart';

/// Bridge to the Android call-screening service. On iPhone these do nothing:
/// iOS does not let apps screen calls, so calls reach Chintan only when you
/// decline them (carrier forwarding).
class NativeScreening {
  static const _ch = MethodChannel('chintan/native');

  static bool get supported => Platform.isAndroid;

  static Future<bool> hasRole() async {
    if (!supported) return false;
    return await _ch.invokeMethod<bool>('hasRole') ?? false;
  }

  static Future<bool> requestRole() async {
    if (!supported) return false;
    return await _ch.invokeMethod<bool>('requestRole') ?? false;
  }

  /// mode: "all" (every call, saved contacts too), "unknown" (only numbers not in contacts), "off".
  static Future<void> configure({required String mode, required int snoozedUntilMs}) async {
    if (!supported) return;
    await _ch.invokeMethod('configure', {'mode': mode, 'snoozedUntilMs': snoozedUntilMs});
  }
}
