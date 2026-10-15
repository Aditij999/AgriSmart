import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Device speech recognition used to dictate chatbot questions.
///
/// Recognized words are handed back as plain text so the caller can put them in
/// the normal chat input field; no audio ever leaves the phone.
class SpeechInputService extends ChangeNotifier {
  SpeechInputService({stt.SpeechToText? speech})
    : _speech = speech ?? stt.SpeechToText();

  final stt.SpeechToText _speech;
  bool _initialized = false;
  bool _listening = false;
  String? _error;

  bool get isListening => _listening;

  /// Last failure message shown to the user, or null.
  String? get error => _error;

  void clearError() {
    if (_error == null) return;
    _error = null;
    notifyListeners();
  }

  Future<bool> _ensureInitialized() async {
    if (_initialized) return true;
    try {
      _initialized = await _speech.initialize(
        onStatus: _onStatus,
        onError: (error) => _fail(_messageForError(error.errorMsg)),
      );
    } catch (failure) {
      debugPrint('Speech initialize failed: $failure');
      _initialized = false;
    }
    if (!_initialized) {
      _fail(
        'Speech recognition is unavailable — check the microphone '
        'permission and that a speech service is installed.',
      );
    }
    return _initialized;
  }

  /// Starts listening. [onResult] receives the transcript so far; [isFinal] is
  /// true for the last result of the utterance.
  Future<void> start({
    required void Function(String text, bool isFinal) onResult,
  }) async {
    if (_listening) return;
    _error = null;
    notifyListeners();

    if (!await _ensureInitialized()) return;
    if (!await _speech.hasPermission) {
      _fail(
        'Microphone permission denied. Enable it in system settings to '
        'use voice input.',
      );
      return;
    }

    try {
      await _speech.listen(
        onResult: (result) {
          final words = result.recognizedWords.trim();
          if (result.finalResult && words.isEmpty) {
            _fail("Didn't catch that — please try again.");
            return;
          }
          onResult(words, result.finalResult);
          if (result.finalResult) _setListening(false);
        },
        listenOptions: stt.SpeechListenOptions(
          listenMode: stt.ListenMode.dictation,
          partialResults: true,
          cancelOnError: true,
          pauseFor: const Duration(seconds: 3),
          listenFor: const Duration(seconds: 30),
        ),
      );
      _setListening(true);
    } catch (failure) {
      debugPrint('Speech listen failed: $failure');
      _fail('Could not start listening. Please try again.');
    }
  }

  Future<void> stop() async {
    if (!_listening) return;
    try {
      await _speech.stop();
    } catch (failure) {
      debugPrint('Speech stop failed: $failure');
    }
    _setListening(false);
  }

  Future<void> cancel() async {
    if (!_listening) return;
    try {
      await _speech.cancel();
    } catch (failure) {
      debugPrint('Speech cancel failed: $failure');
    }
    _setListening(false);
  }

  void _onStatus(String status) {
    final listening = status == stt.SpeechToText.listeningStatus;
    if (listening != _listening) _setListening(listening);
  }

  void _setListening(bool value) {
    if (_listening == value) return;
    _listening = value;
    notifyListeners();
  }

  void _fail(String message) {
    _error = message;
    _listening = false;
    notifyListeners();
  }

  String _messageForError(String code) {
    switch (code) {
      case 'error_permission':
      case 'error_audio_error':
        return 'Microphone unavailable — check the app permission.';
      case 'error_no_match':
      case 'error_speech_timeout':
        return "Didn't catch that — please try again.";
      case 'error_network':
      case 'error_network_timeout':
        return 'Speech recognition needs a network connection right now.';
      case 'error_busy':
        return 'Speech recognition is busy. Please try again.';
      default:
        return 'Speech recognition error ($code).';
    }
  }
}
