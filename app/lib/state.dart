import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'api.dart';
import 'native.dart';

/// Everything the screens need: the call log, settings, and live updates.
class AppState extends ChangeNotifier {
  late SharedPreferences _prefs;
  Api api = Api('', '');

  List<Map<String, dynamic>> calls = [];
  Map<String, dynamic> settings = {};
  Map<String, String> categories = {};
  bool connected = false;
  String? error;
  String screeningMode = 'all';

  /// Turns that arrived live, per call, so open call screens update instantly.
  final Map<String, List<Map<String, dynamic>>> liveTurns = {};

  WebSocketChannel? _ws;
  StreamSubscription? _wsSub;
  Timer? _reconnect;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    screeningMode = _prefs.getString('screening_mode') ?? 'all';
    api = Api(_prefs.getString('server_url') ?? '', _prefs.getString('app_token') ?? '');
    if (api.configured) {
      await refresh();
      _connect();
    }
  }

  Future<void> saveServer(String url, String token) async {
    await _prefs.setString('server_url', url.trim());
    await _prefs.setString('app_token', token.trim());
    api = Api(url.trim(), token.trim());
    _disconnect();
    await refresh();
    _connect();
  }

  // --- data ---
  Future<void> refresh() async {
    if (!api.configured) return;
    try {
      final r = await api.get('/api/calls') as Map<String, dynamic>;
      calls = List<Map<String, dynamic>>.from(r['calls'] as List);
      categories = Map<String, String>.from(r['categories'] as Map);
      final s = await api.get('/api/settings') as Map<String, dynamic>;
      settings = s;
      error = null;
      await _syncNative();
    } catch (e) {
      error = e.toString();
    }
    notifyListeners();
  }

  bool get snoozed => ((settings['snoozed_until'] as num?) ?? 0) * 1000 > DateTime.now().millisecondsSinceEpoch;

  DateTime? get snoozedUntil {
    final v = (settings['snoozed_until'] as num?) ?? 0;
    return v > 0 ? DateTime.fromMillisecondsSinceEpoch((v * 1000).round()) : null;
  }

  List<String> get quickReplies => List<String>.from((settings['quick_replies'] as List?) ?? const []);

  String categoryLabel(String? key) => categories[key] ?? (key ?? 'Unclear');

  Future<void> snooze(int minutes) async {
    final s = await api.post('/api/snooze', {'minutes': minutes}) as Map<String, dynamic>;
    settings.addAll(s);
    await _syncNative();
    notifyListeners();
  }

  Future<void> setScreeningMode(String mode) async {
    screeningMode = mode;
    await _prefs.setString('screening_mode', mode);
    await _syncNative();
    notifyListeners();
  }

  Future<void> _syncNative() async {
    final until = snoozed ? snoozedUntil!.millisecondsSinceEpoch : 0;
    try {
      await NativeScreening.configure(mode: screeningMode, snoozedUntilMs: until);
    } catch (_) {}
  }

  Future<void> saveSettings(Map<String, dynamic> values) async {
    final s = await api.put('/api/settings', values) as Map<String, dynamic>;
    settings.addAll(s);
    notifyListeners();
  }

  Future<void> mute(String number) async {
    final r = await api.post('/api/muted', {'number': number}) as Map<String, dynamic>;
    settings['muted'] = r['muted'];
    notifyListeners();
  }

  Future<void> unmute(String number) async {
    final r = await api.delete('/api/muted/${Uri.encodeComponent(number)}') as Map<String, dynamic>;
    settings['muted'] = r['muted'];
    notifyListeners();
  }

  Future<void> deleteCall(String id) async {
    await api.delete('/api/calls/$id');
    calls.removeWhere((c) => c['id'] == id);
    notifyListeners();
  }

  // --- live call controls ---
  void sendLive(String type, String callId, [String? text]) {
    final msg = {'type': type, 'call_id': callId, if (text != null) 'text': text};
    if (_ws != null && connected) {
      _ws!.sink.add(jsonEncode(msg));
    } else {
      api.post('/api/calls/$callId/$type', text == null ? null : {'text': text}).catchError((_) => null);
    }
  }

  // --- websocket ---
  void _connect() {
    if (!api.configured) return;
    try {
      _ws = WebSocketChannel.connect(api.socketUri());
      _wsSub = _ws!.stream.listen(_onEvent, onDone: _scheduleReconnect, onError: (_) => _scheduleReconnect());
      connected = true;
    } catch (_) {
      _scheduleReconnect();
    }
    notifyListeners();
  }

  void _disconnect() {
    _reconnect?.cancel();
    _wsSub?.cancel();
    _ws?.sink.close();
    _ws = null;
    connected = false;
  }

  void _scheduleReconnect() {
    connected = false;
    notifyListeners();
    _reconnect?.cancel();
    _reconnect = Timer(const Duration(seconds: 5), () {
      _disconnect();
      _connect();
    });
  }

  void _onEvent(dynamic raw) {
    final ev = jsonDecode(raw as String) as Map<String, dynamic>;
    switch (ev['type']) {
      case 'turn':
        liveTurns.putIfAbsent(ev['call_id'] as String, () => []).add(ev);
        break;
      case 'call_updated':
        final call = Map<String, dynamic>.from(ev['call'] as Map);
        final i = calls.indexWhere((c) => c['id'] == call['id']);
        if (i >= 0) {
          calls[i] = call;
        } else {
          calls.insert(0, call);
        }
        break;
      case 'settings':
        settings['snoozed_until'] = ev['snoozed_until'];
        _syncNative();
        break;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _disconnect();
    super.dispose();
  }
}
