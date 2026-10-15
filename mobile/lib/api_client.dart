/// HTTP client for the AgriSmart FastAPI backend.
///
/// Base URL defaults to the Android emulator's host loopback. Override with:
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  final http.Client _client;
  String? _token;

  void setToken(String? token) => _token = token;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  Uri _uri(String path, [Map<String, dynamic>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Future<dynamic> _send(Future<http.Response> Function() request) async {
    late http.Response response;
    try {
      response = await request().timeout(const Duration(seconds: 90));
    } catch (error) {
      throw ApiException(
          'Cannot reach the server at $baseUrl. Is the backend running?');
    }

    final body = response.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));

    if (response.statusCode >= 400) {
      final detail = body is Map ? body['detail'] : null;
      throw ApiException(
        detail is String ? detail : 'Request failed (${response.statusCode})',
        statusCode: response.statusCode,
      );
    }
    return body;
  }

  Future<Map<String, dynamic>> register({
    required String username,
    required String password,
    String? email,
    String? fullName,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/api/auth/register'),
          headers: _headers,
          body: jsonEncode({
            'username': username,
            'password': password,
            if (email != null && email.isNotEmpty) 'email': email,
            if (fullName != null && fullName.isNotEmpty) 'full_name': fullName,
          }),
        ));
    return (body as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/api/auth/login'),
          headers: _headers,
          body: jsonEncode({'username': username, 'password': password}),
        ));
    return (body as Map).cast<String, dynamic>();
  }

  Future<User> me() async {
    final body = await _send(() => _client.get(_uri('/api/auth/me'), headers: _headers));
    return User.fromJson((body as Map).cast<String, dynamic>());
  }

  Future<List<String>> crops() async {
    final body = await _send(() => _client.get(_uri('/api/crops'), headers: _headers));
    return (body as List).map((item) => item as String).toList();
  }

  Future<PredictionResult> predict({
    required SoilInput soil,
    String? crop,
    String? label,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/api/predict'),
          headers: _headers,
          body: jsonEncode({
            ...soil.toJson(),
            if (crop != null) 'crop': crop,
            if (label != null && label.isNotEmpty) 'label': label,
          }),
        ));
    return PredictionResult.fromJson((body as Map).cast<String, dynamic>());
  }

  Future<({int total, List<HistoryItem> items})> history({
    int limit = 50,
    int offset = 0,
  }) async {
    final body = await _send(() => _client.get(
          _uri('/api/history', {'limit': '$limit', 'offset': '$offset'}),
          headers: _headers,
        ));
    final map = (body as Map).cast<String, dynamic>();
    return (
      total: map['total'] as int,
      items: (map['items'] as List)
          .map((item) => HistoryItem.fromJson((item as Map).cast<String, dynamic>()))
          .toList(),
    );
  }

  Future<PredictionResult> historyEntry(int id) async {
    final body =
        await _send(() => _client.get(_uri('/api/history/$id'), headers: _headers));
    return PredictionResult.fromJson((body as Map).cast<String, dynamic>());
  }

  /// Crop-rotation warnings for the signed-in user (same rules as the website).
  Future<List<RotationAdvice>> rotationAlerts() async {
    final body = await _send(
        () => _client.get(_uri('/api/history/rotation'), headers: _headers));
    return ((body as Map)['alerts'] as List)
        .map((item) => RotationAdvice.fromJson((item as Map).cast<String, dynamic>()))
        .toList();
  }

  /// Records which crop the farmer finally grew on a saved run — the input the
  /// rotation check is based on.
  Future<void> setGrownCrop(int id, String crop) async {
    await _send(() => _client.patch(
          _uri('/api/history/$id'),
          headers: _headers,
          body: jsonEncode({'grown_crop': crop}),
        ));
  }

  Future<CompareResult> compare(List<int> ids) async {
    final query = ids.map((id) => 'ids=$id').join('&');
    final body = await _send(() => _client.get(
          Uri.parse('$baseUrl/api/history/compare?$query'),
          headers: _headers,
        ));
    return CompareResult.fromJson((body as Map).cast<String, dynamic>());
  }

  Future<void> deleteHistoryEntry(int id) async {
    await _send(() => _client.delete(_uri('/api/history/$id'), headers: _headers));
  }

  Future<int> clearHistory() async {
    final body =
        await _send(() => _client.delete(_uri('/api/history'), headers: _headers));
    return ((body as Map)['deleted'] as num).toInt();
  }

  /// [lang] is the reply language: 'auto' (default) detects Hindi/Marathi/
  /// English from [message] itself; 'en' / 'hi' / 'mr' forces a language
  /// regardless of what script the user typed in.
  Future<({String answer, String answerPlain, String source, String lang})>
      chat({
    required String message,
    required List<ChatMessage> history,
    int? predictionId,
    String lang = 'auto',
  }) async {
    final body = await _send(() => _client.post(
          _uri('/api/chat'),
          headers: _headers,
          body: jsonEncode({
            'message': message,
            'history': history.map((turn) => turn.toJson()).toList(),
            if (predictionId != null) 'prediction_id': predictionId,
            'lang': lang,
          }),
        ));
    final map = (body as Map).cast<String, dynamic>();
    return (
      answer: map['answer'] as String,
      answerPlain: map['answer_plain'] as String,
      source: map['source'] as String,
      lang: (map['lang'] as String?) ?? lang,
    );
  }
}
