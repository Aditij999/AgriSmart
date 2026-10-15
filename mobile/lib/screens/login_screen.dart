import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../theme.dart';
import '../widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _fullName = TextEditingController();
  final _email = TextEditingController();

  bool _registerMode = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _fullName.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });

    final state = context.read<AppState>();
    try {
      if (_registerMode) {
        await state.register(
          username: _username.text.trim(),
          password: _password.text,
          email: _email.text.trim(),
          fullName: _fullName.text.trim(),
        );
      } else {
        await state.login(_username.text.trim(), _password.text);
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Dark forest header card — same as the website's login page.
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 24, vertical: 28),
                      decoration: BoxDecoration(
                        color: kSidebar,
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: kPaperShadow,
                      ),
                      child: Column(
                        children: [
                          Text('FIELD COMPANION',
                              style: monoLabelStyle(color: kGold, size: 10)),
                          const SizedBox(height: 8),
                          Text.rich(
                            TextSpan(
                              style: displayStyle(
                                  size: 34, color: kSidebarText),
                              children: [
                                const TextSpan(text: 'AgriSmart '),
                                TextSpan(
                                    text: 'DSS',
                                    style: displayStyle(size: 34, color: kGold)),
                                const TextSpan(text: ' 🌾'),
                              ],
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'Crop, soil, fertilizer and yield decisions for your field.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                              color: kSidebarText.withValues(alpha: 0.7),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 28),
                    if (_error != null) ...[
                      ErrorBanner(message: _error!),
                      const SizedBox(height: 16),
                    ],
                    TextFormField(
                      controller: _username,
                      decoration: const InputDecoration(labelText: 'Username'),
                      textInputAction: TextInputAction.next,
                      validator: (value) => (value == null || value.trim().length < 3)
                          ? 'At least 3 characters'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _password,
                      decoration: const InputDecoration(labelText: 'Password'),
                      obscureText: true,
                      validator: (value) => (value == null || value.length < 6)
                          ? 'At least 6 characters'
                          : null,
                    ),
                    if (_registerMode) ...[
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _fullName,
                        decoration: const InputDecoration(labelText: 'Full name (optional)'),
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _email,
                        decoration: const InputDecoration(labelText: 'Email (optional)'),
                        keyboardType: TextInputType.emailAddress,
                      ),
                    ],
                    const SizedBox(height: 22),
                    FilledButton(
                      onPressed: _busy ? null : _submit,
                      child: _busy
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white))
                          : Text(_registerMode ? 'Create account' : 'Log in'),
                    ),
                    TextButton(
                      onPressed: _busy
                          ? null
                          : () => setState(() {
                                _registerMode = !_registerMode;
                                _error = null;
                              }),
                      child: Text(_registerMode
                          ? 'Already registered? Log in'
                          : 'New here? Create an account'),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Server: ${ApiClient.baseUrl}',
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 11, color: Color(0xFF68756D)),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
