import 'package:flutter/material.dart';

/// Colours carried over from the web mockup: dark ink, paper text, teal accent.
class C {
  static const ink = Color(0xFF1B2430);
  static const ink2 = Color(0xFF232E3C);
  static const paper = Color(0xFFEDEAE2);
  static const paperDim = Color(0xFFB9B5AB);
  static const teal = Color(0xFF3F8A78);
  static const rose = Color(0xFFE38F76);
  static const red = Color(0xFFFF6B5B);
  static const amber = Color(0xFFE0B04F);
}

ThemeData chintanTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(seedColor: C.teal, brightness: Brightness.dark, surface: C.ink),
    scaffoldBackgroundColor: C.ink,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(backgroundColor: C.ink, foregroundColor: C.paper, elevation: 0),
    cardTheme: const CardThemeData(color: C.ink2, margin: EdgeInsets.symmetric(horizontal: 12, vertical: 5)),
  );
}

Color categoryColor(String? category) {
  switch (category) {
    case 'spam_scam':
      return C.red;
    case 'regulatory':
      return C.rose;
    case 'client_deadline':
    case 'client_general':
      return C.teal;
    case 'bank':
    case 'sales':
      return C.amber;
    case 'personal':
      return const Color(0xFF8FA8E3);
    default:
      return C.paperDim;
  }
}

class CategoryChip extends StatelessWidget {
  const CategoryChip(this.label, this.category, {super.key});
  final String label;
  final String? category;

  @override
  Widget build(BuildContext context) {
    final c = categoryColor(category);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: c.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(6)),
      child: Text(label, style: TextStyle(color: c, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}

String formatTime(num? unixSeconds) {
  if (unixSeconds == null) return '';
  final t = DateTime.fromMillisecondsSinceEpoch((unixSeconds * 1000).round());
  final now = DateTime.now();
  final hm = '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  if (t.year == now.year && t.month == now.month && t.day == now.day) return hm;
  return '${t.day}/${t.month} $hm';
}
