import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'theme.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => AppState()..restoreSession(),
      child: const AgriSmartApp(),
    ),
  );
}

class AgriSmartApp extends StatelessWidget {
  const AgriSmartApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AgriSmart DSS',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: Consumer<AppState>(
        builder: (context, state, _) {
          if (state.restoring) {
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          }
          return state.isLoggedIn ? const HomeShell() : const LoginScreen();
        },
      ),
    );
  }
}
