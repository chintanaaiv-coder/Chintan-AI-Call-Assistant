import 'dart:convert';

import 'package:http/http.dart' as http;

/// Talks to the Chintan server.
class Api {
  Api(this.baseUrl, this.token);

  final String baseUrl;
  final String token;

  bool get configured => baseUrl.isNotEmpty && token.isNotEmpty;

  String get _root => baseUrl.trim().replaceAll(RegExp(r'/+$'), '');

  Uri _uri(String path, [Map<String, String>? query]) {
    final u = Uri.parse('$_root$path');
    return query == null ? u : u.replace(queryParameters: query);
  }

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  Future<dynamic> _send(Future<http.Response> req) async {
    final r = await req.timeout(const Duration(seconds: 20));
    if (r.statusCode >= 400) {
      String msg = 'Server error ${r.statusCode}';
      try {
        msg = (jsonDecode(r.body) as Map)['detail'].toString();
      } catch (_) {}
      throw ApiError(msg);
    }
    return r.body.isEmpty ? null : jsonDecode(r.body);
  }

  Future<dynamic> get(String path) => _send(http.get(_uri(path), headers: _headers));

  Future<dynamic> post(String path, [Object? body]) =>
      _send(http.post(_uri(path), headers: _headers, body: jsonEncode(body ?? {})));

  Future<dynamic> put(String path, Object body) =>
      _send(http.put(_uri(path), headers: _headers, body: jsonEncode(body)));

  Future<dynamic> delete(String path) => _send(http.delete(_uri(path), headers: _headers));

  Future<Map<String, dynamic>> health() async {
    final r = await http.get(_uri('/health')).timeout(const Duration(seconds: 15));
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  String recordingUrl(String callId) => _uri('/api/calls/$callId/recording', {'token': token}).toString();

  Uri socketUri() {
    final u = _uri('/ws', {'token': token});
    return u.replace(scheme: u.scheme == 'https' ? 'wss' : 'ws');
  }
}

class ApiError implements Exception {
  ApiError(this.message);
  final String message;
  @override
  String toString() => message;
}
