import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../app_state.dart';
import '../theme.dart';
import '../widgets.dart';
import 'chat_screen.dart';
import 'dashboard_screen.dart';
import 'history_screen.dart';
import 'predict_screen.dart';

/// Bottom-nav shell. The history tab is rebuilt on selection so it always
/// reflects predictions made in the other tabs.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;
  Key _historyKey = UniqueKey();

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AppState>().user;
    final name = userDisplayName(user);
    final pages = [
      DashboardScreen(onNewAnalysis: () => setState(() => _index = 1)),
      const PredictScreen(),
      HistoryScreen(key: _historyKey),
      const ChatScreen(),
    ];

    return Scaffold(
      // Brand + signed-in avatar, mirroring the website's sidebar brand and top bar.
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: kSidebar,
                border: Border.all(color: kGold, width: 1.5),
              ),
              child: const Icon(Icons.eco_outlined, size: 18, color: kGold),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('AgriSmart', style: displayStyle(size: 19, weight: FontWeight.w700)),
                Text('FIELD COMPANION', style: monoLabelStyle(size: 8.5)),
              ],
            ),
          ],
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Account',
            offset: const Offset(0, 48),
            onSelected: (value) {
              if (value == 'logout') context.read<AppState>().logout();
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                enabled: false,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        style: const TextStyle(
                            fontWeight: FontWeight.w800, color: kDark)),
                    const Text('Synced with the website',
                        style: TextStyle(fontSize: 11, color: kSoft)),
                  ],
                ),
              ),
              const PopupMenuItem(value: 'logout', child: Text('Log out')),
            ],
            child: Padding(
              padding: const EdgeInsets.only(right: 16),
              child: CircleAvatar(
                radius: 19,
                backgroundColor: kSecondary,
                child: Text(
                  initialsOf(name),
                  style: const TextStyle(
                      fontSize: 12, fontWeight: FontWeight.w800, color: kAccent),
                ),
              ),
            ),
          ),
        ],
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, thickness: 1, color: kBorder),
        ),
      ),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (index) => setState(() {
          _index = index;
          if (index == 2) _historyKey = UniqueKey();
        }),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.science_outlined), label: 'Predict'),
          NavigationDestination(icon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'Chat'),
        ],
      ),
    );
  }
}
