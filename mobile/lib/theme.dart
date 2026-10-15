import 'package:flutter/material.dart';

/// AgriSmart palette (paper, forest green, gold) matching the Streamlit dashboard.
const Color kAccent = Color(0xFF244F3B);
const Color kClay = Color(0xFFB07D14); // darker gold so it stays readable as text
const Color kBackground = Color(0xFFF8F6EF);
const Color kSurface = Color(0xFFFCFAF5);
const Color kBorder = Color(0xFFDCD8CC);
const Color kDark = Color(0xFF213329);
const Color kWarn = Color(0xFF8A6414);
const Color kDanger = Color(0xFFB9483D);

// Remaining tokens from the website's CSS (:root in app.py) so both clients
// draw from the same palette.
const Color kGold = Color(0xFFE9B84B); // --accent
const Color kSecondary = Color(0xFFEEE8D9); // --secondary / chips / avatar
const Color kSoft = Color(0xFF68756D); // --soft (captions)
const Color kMid = Color(0xFF4D5D54); // --mid
const Color kSidebar = Color(0xFF1E3A2B); // dark forest rail -> bottom nav
const Color kSidebarText = Color(0xFFF2EFE6);

/// Display serif (website: Newsreader) and mono eyebrow labels (DM Mono).
/// Those two web fonts are not bundled in the app, so these resolve to the
/// platform's serif / monospace until the font files are added to the project.
const String kDisplayFont = 'serif';
const String kMonoFont = 'monospace';

TextStyle displayStyle({
  double size = 24,
  FontWeight weight = FontWeight.w600,
  Color color = kAccent,
  double? height,
}) =>
    TextStyle(
      fontFamily: kDisplayFont,
      fontSize: size,
      fontWeight: weight,
      color: color,
      letterSpacing: -0.2,
      height: height,
    );

/// Small uppercase eyebrow / tag text. Callers pass already-uppercased text.
TextStyle monoLabelStyle({Color color = kSoft, double size = 10}) => TextStyle(
      fontFamily: kMonoFont,
      fontSize: size,
      letterSpacing: 0.8,
      fontWeight: FontWeight.w500,
      color: color,
    );

/// Soft "paper" shadow used on the website's cards.
const List<BoxShadow> kPaperShadow = [
  BoxShadow(color: Color(0x12213329), blurRadius: 24, offset: Offset(0, 8)),
  BoxShadow(color: Color(0x0A213329), blurRadius: 6, offset: Offset(0, 2)),
];

ThemeData buildTheme() {
  final base = ThemeData(
    colorScheme: ColorScheme.fromSeed(seedColor: kAccent, surface: kSurface),
    useMaterial3: true,
  );
  return base.copyWith(
    scaffoldBackgroundColor: kBackground,
    appBarTheme: const AppBarTheme(
      backgroundColor: kBackground,
      foregroundColor: kDark,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    cardTheme: CardThemeData(
      color: kSurface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: kBorder),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kSurface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: kBorder),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: kAccent,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    // The website's dark forest sidebar, as a bottom bar: gold pill on the
    // active destination, cream text on forest green otherwise.
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: kSidebar,
      indicatorColor: kGold,
      surfaceTintColor: Colors.transparent,
      iconTheme: WidgetStateProperty.resolveWith((states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? kDark
                : kSidebarText.withValues(alpha: 0.75),
          )),
      labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
            fontSize: 12,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
            color: states.contains(WidgetState.selected)
                ? kGold
                : kSidebarText.withValues(alpha: 0.75),
          )),
    ),
  );
}

Color statusColor(String status) {
  switch (status) {
    case 'Optimal':
      return kAccent;
    case 'Low':
      return kDanger;
    case 'High':
      return kWarn;
    default:
      return kDark;
  }
}
