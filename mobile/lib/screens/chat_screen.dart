import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../models.dart';
import '../theme.dart';
import '../voice/speech_input_service.dart';
import '../voice/tts_service.dart';
import '../widgets.dart';

/// Chat with the existing hybrid intent-classifier + Gemini assistant.
///
/// The backend answers about the given history entry (or the latest one).
/// Speech recognition and text-to-speech run on the device: dictation only
/// fills the input field, and answers are spoken from `answer_plain`.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.predictionId});

  final int? predictionId;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

/// Reply-language options shown to the user. 'auto' detects Hindi/Marathi/
/// English from what they type; the others force a language regardless of
/// the script used, matching the backend's ChatRequest.lang values.
const _kLanguageOptions = <String, String>{
  'auto': 'Auto',
  'en': 'English',
  'hi': 'हिंदी',
  'mr': 'मराठी',
};

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  final _speech = SpeechInputService();
  final _tts = TtsService();
  bool _busy = false;
  String _lang = 'auto';

  /// Text already in the field when dictation started, so partial results
  /// replace only the dictated part.
  String _textBeforeDictation = '';

  @override
  void initState() {
    super.initState();
    _speech.addListener(_onVoiceStateChanged);
    _tts.addListener(_onVoiceStateChanged);
  }

  @override
  void dispose() {
    _speech.removeListener(_onVoiceStateChanged);
    _tts.removeListener(_onVoiceStateChanged);
    _speech.cancel();
    _speech.dispose();
    _tts.dispose();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onVoiceStateChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _toggleListening() async {
    if (_speech.isListening) {
      await _speech.stop();
      return;
    }
    // Never listen and speak at the same time.
    await _tts.stop();
    _textBeforeDictation = _controller.text.trimRight();
    await _speech.start(onResult: _onSpeechResult);
  }

  void _onSpeechResult(String text, bool isFinal) {
    if (text.isEmpty) return;
    final prefix = _textBeforeDictation.isEmpty ? '' : '$_textBeforeDictation ';
    _controller.value = TextEditingValue(
      text: '$prefix$text',
      selection: TextSelection.collapsed(offset: prefix.length + text.length),
    );
    // The recognized text stays editable; the user still presses Send.
    if (isFinal) _textBeforeDictation = _controller.text.trimRight();
  }

  Future<void> _toggleSpeaking(int index, ChatMessage message) async {
    final id = 'message-$index';
    if (_tts.isSpeakingMessage(id)) {
      await _tts.stop();
      return;
    }
    await _speech.cancel();
    await _tts.speak(id, message.speakableText, lang: message.lang);
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _busy) return;
    if (_speech.isListening) await _speech.stop();

    setState(() {
      _messages.add(ChatMessage(role: 'user', text: text));
      _busy = true;
      _controller.clear();
    });
    _textBeforeDictation = '';
    _scrollToEnd();

    try {
      final reply = await context.read<AppState>().api.chat(
            message: text,
            // Exclude the message just added — the API appends it itself.
            history: _messages.sublist(0, _messages.length - 1),
            predictionId: widget.predictionId,
            lang: _lang,
          );
      if (!mounted) return;
      setState(
        () => _messages.add(
          ChatMessage(
            role: 'model',
            text: reply.answer,
            source: reply.source,
            plainText: reply.answerPlain,
            lang: reply.lang,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(
        () => _messages.add(
          ChatMessage(role: 'model', text: error.message, source: 'fallback'),
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollToEnd();
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
          child: Row(
            children: [
              const Text('Reply in:', style: TextStyle(fontSize: 12, color: Color(0xFF68756D))),
              const SizedBox(width: 8),
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _kLanguageOptions.entries.map((entry) {
                      final selected = _lang == entry.key;
                      return Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ChoiceChip(
                          label: Text(entry.value),
                          selected: selected,
                          onSelected: (_) => setState(() => _lang = entry.key),
                          selectedColor: kAccent,
                          labelStyle: TextStyle(
                            color: selected ? Colors.white : kDark,
                            fontSize: 12,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: _messages.isEmpty
              ? const EmptyState(
                  icon: Icons.chat_bubble_outline,
                  message:
                      'Ask about your latest analysis — why a crop was recommended, '
                      'which fertilizer to apply, or what the yield estimate means. '
                      'Ask in English, Hindi, or Marathi, or pick a language above, '
                      'and use the mic to speak your question.',
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final message = _messages[index];
                    final bubble = Container(
                      padding: const EdgeInsets.all(12),
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(context).size.width * 0.70,
                      ),
                      decoration: BoxDecoration(
                        color: kSecondary,
                        border: Border.all(color: kBorder),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            message.text,
                            style: const TextStyle(color: kDark, height: 1.4),
                          ),
                          if (!message.isUser)
                            _SpeakButton(
                              speaking: _tts.isSpeakingMessage(
                                'message-$index',
                              ),
                              onPressed: () => _toggleSpeaking(index, message),
                            ),
                          if (message.source != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(
                                message.source == 'gemini'
                                    ? 'Gemini'
                                    : message.source == 'intent'
                                        ? '⚡ Answered instantly — no API call needed.'
                                        : 'Unavailable',
                                style: const TextStyle(
                                  fontSize: 10,
                                  color: kSoft,
                                ),
                              ),
                            ),
                        ],
                      ),
                    );
                    final avatar = _ChatAvatar(isUser: message.isUser);
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: message.isUser
                            ? MainAxisAlignment.end
                            : MainAxisAlignment.start,
                        children: message.isUser
                            ? [bubble, const SizedBox(width: 8), avatar]
                            : [avatar, const SizedBox(width: 8), bubble],
                      ),
                    );
                  },
                ),
        ),
        if (_busy) const LinearProgressIndicator(minHeight: 2, color: kAccent),
        _VoiceStatusBar(
          listening: _speech.isListening,
          speaking: _tts.isSpeaking,
          message: _speech.error ?? _tts.error,
          onStopSpeaking: _tts.stop,
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
          child: Row(
            children: [
              IconButton(
                tooltip: _speech.isListening
                    ? 'Stop listening'
                    : 'Speak your question',
                onPressed: _busy ? null : _toggleListening,
                color: _speech.isListening ? Colors.red : kAccent,
                icon: Icon(_speech.isListening ? Icons.mic : Icons.mic_none),
              ),
              Expanded(
                child: TextField(
                  controller: _controller,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(
                    hintText: 'Ask about your results…',
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 12,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                style: IconButton.styleFrom(backgroundColor: kAccent),
                onPressed: _busy ? null : _send,
                icon: const Icon(Icons.send),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Small rounded avatar beside each message (website: red for you, gold for the assistant).
class _ChatAvatar extends StatelessWidget {
  const _ChatAvatar({required this.isUser});

  final bool isUser;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        color: isUser ? const Color(0xFFE5484D) : const Color(0xFFF0A92B),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Icon(
        isUser ? Icons.face_outlined : Icons.smart_toy_outlined,
        size: 18,
        color: Colors.white,
      ),
    );
  }
}

/// Read-aloud / stop control shown under an assistant answer.
class _SpeakButton extends StatelessWidget {
  const _SpeakButton({required this.speaking, required this.onPressed});

  final bool speaking;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: TextButton.icon(
        onPressed: onPressed,
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          minimumSize: const Size(0, 32),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          foregroundColor: speaking ? Colors.red : kAccent,
        ),
        icon: Icon(
          speaking ? Icons.stop_circle_outlined : Icons.volume_up,
          size: 18,
        ),
        label: Text(
          speaking ? 'Stop' : 'Listen',
          style: const TextStyle(fontSize: 12),
        ),
      ),
    );
  }
}

/// Shows listening / speaking / error state above the input row.
class _VoiceStatusBar extends StatelessWidget {
  const _VoiceStatusBar({
    required this.listening,
    required this.speaking,
    required this.message,
    required this.onStopSpeaking,
  });

  final bool listening;
  final bool speaking;
  final String? message;
  final VoidCallback onStopSpeaking;

  @override
  Widget build(BuildContext context) {
    final IconData icon;
    final String label;
    final Color color;
    if (message != null && !listening && !speaking) {
      icon = Icons.error_outline;
      label = message!;
      color = Colors.red;
    } else if (listening) {
      icon = Icons.mic;
      label = 'Listening… tap the mic again to stop.';
      color = Colors.red;
    } else if (speaking) {
      icon = Icons.volume_up;
      label = 'Speaking the answer…';
      color = kAccent;
    } else {
      return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Expanded(
            child: Text(label, style: TextStyle(fontSize: 12, color: color)),
          ),
          if (speaking)
            TextButton(
              onPressed: onStopSpeaking,
              style: TextButton.styleFrom(
                minimumSize: const Size(0, 28),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: const Text('Stop', style: TextStyle(fontSize: 12)),
            ),
        ],
      ),
    );
  }
}
