import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'models.dart';
import 'theme.dart';

final DateFormat kDateFormat = DateFormat('d MMM yyyy, HH:mm');

/// Capitalises the first letter of each word ("dia" -> "Dia", "ravi kumar" ->
/// "Ravi Kumar"). Usernames are stored lower-case, so every place that shows a
/// name goes through here. Mirrors `_display_name()` in the website's app.py.
String displayName(String? raw) => (raw ?? '')
    .trim()
    .split(RegExp(r'\s+'))
    .where((word) => word.isNotEmpty)
    .map((word) => word[0].toUpperCase() + word.substring(1))
    .join(' ');

/// The name to greet / label a signed-in user with: full name if they gave one,
/// otherwise their username, capitalised.
String userDisplayName(User? user) {
  if (user == null) return '';
  final full = user.fullName;
  return displayName(full != null && full.trim().isNotEmpty ? full : user.username);
}

/// Two-letter avatar initials, same as the website's top bar.
String initialsOf(String name) {
  final clean = name.trim();
  if (clean.isEmpty) return 'G';
  return (clean.length >= 2 ? clean.substring(0, 2) : clean).toUpperCase();
}

class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.title,
    required this.child,
    this.icon,
    this.subtitle,
    this.tag,
  });

  final String title;
  final Widget child;
  final IconData? icon;

  /// Optional grey helper line under the title (website: `.card-sub`).
  final String? subtitle;

  /// Optional small uppercase tag at the top-right (website: `.card-tag`).
  final String? tag;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: kPaperShadow,
      ),
      child: Card(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: kBorder),
        ),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (icon != null) ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Icon(icon, size: 18, color: kAccent),
                    ),
                    const SizedBox(width: 8),
                  ],
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 16,
                              color: kAccent),
                        ),
                        if (subtitle != null) ...[
                          const SizedBox(height: 4),
                          Text(
                            subtitle!,
                            style: const TextStyle(
                                fontSize: 12.5, height: 1.45, color: kSoft),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (tag != null) ...[
                    const SizedBox(width: 8),
                    Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Text(tag!.toUpperCase(),
                          style: monoLabelStyle(size: 9)),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 14),
              child,
            ],
          ),
        ),
      ),
    );
  }
}

/// Section heading with the website's gold left rule (`.section-header`).
class SectionHeading extends StatelessWidget {
  const SectionHeading(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: 12),
      decoration: const BoxDecoration(
        border: Border(left: BorderSide(color: kGold, width: 4)),
      ),
      child: Text(text, style: displayStyle(size: 22)),
    );
  }
}

class StatTile extends StatelessWidget {
  const StatTile({super.key, required this.label, required this.value, this.hint});

  final String label;
  final String value;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        boxShadow: kPaperShadow,
      ),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label.toUpperCase(), style: monoLabelStyle(size: 9.5)),
              const SizedBox(height: 8),
              Text(value,
                  style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.3,
                      color: kAccent)),
              if (hint != null) ...[
                const SizedBox(height: 4),
                Text(hint!, style: const TextStyle(fontSize: 11, color: kSoft)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8E6E3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kDanger.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: kDanger, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(message, style: const TextStyle(color: kDanger))),
          if (onRetry != null)
            TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.message, this.icon = Icons.eco_outlined});

  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: kBorder),
            const SizedBox(height: 12),
            Text(message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF68756D))),
          ],
        ),
      ),
    );
  }
}

String formatYield(double? kgPerHa) {
  if (kgPerHa == null) return '—';
  return '${NumberFormat('#,##0').format(kgPerHa)} kg/ha';
}
