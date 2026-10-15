/// Session state: auth token persistence and the most recent prediction.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'models.dart';

class AppState extends ChangeNotifier {
  AppState({ApiClient? api}) : api = api ?? ApiClient();

  static const _tokenKey = 'agrismart_token';

  final ApiClient api;

  User? user;
  bool restoring = true;
  PredictionResult? latestPrediction;

  bool get isLoggedIn => user != null;

  /// Bumped whenever the signed-in user's saved runs change (new run, grown crop
  /// recorded, run deleted). Widgets that show history-derived data — like the
  /// crop-rotation alerts — reload when it changes.
  int historyRevision = 0;

  void bumpHistory() {
    historyRevision++;
    notifyListeners();
  }

  Future<void> restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_tokenKey);
    if (token != null) {
      api.setToken(token);
      try {
        user = await api.me();
      } on ApiException {
        api.setToken(null);
        await prefs.remove(_tokenKey);
      }
    }
    restoring = false;
    notifyListeners();
  }

  Future<void> _storeSession(Map<String, dynamic> response) async {
    final token = response['access_token'] as String;
    api.setToken(token);
    user = User.fromJson((response['user'] as Map).cast<String, dynamic>());
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    await _storeSession(await api.login(username: username, password: password));
  }

  Future<void> register({
    required String username,
    required String password,
    String? email,
    String? fullName,
  }) async {
    await _storeSession(await api.register(
      username: username,
      password: password,
      email: email,
      fullName: fullName,
    ));
  }

  Future<void> logout() async {
    api.setToken(null);
    user = null;
    latestPrediction = null;
    historyRevision = 0;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    notifyListeners();
  }

  void setLatestPrediction(PredictionResult prediction) {
    latestPrediction = prediction;
    historyRevision++; // a new run was saved to the account
    notifyListeners();
  }
}
