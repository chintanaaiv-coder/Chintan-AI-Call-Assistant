import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';
import 'call_screen.dart';
import 'settings.dart';
import 'teach.dart';

/// The call log: every screened call, newest first, with its category and summary.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        final s = appState;
        return Scaffold(
          appBar: AppBar(
            title: const Text('Chintan', style: TextStyle(fontWeight: FontWeight.w700)),
            actions: [
              Icon(Icons.circle, size: 10, color: s.connected ? C.teal : C.paperDim),
              IconButton(
                tooltip: 'Test a call',
                icon: const Icon(Icons.science_outlined),
                onPressed: s.api.configured ? () => _startTestCall(context) : null,
              ),
              IconButton(
                tooltip: 'Teach Chintan how I talk',
                icon: const Icon(Icons.record_voice_over_outlined),
                onPressed: s.api.configured
                    ? () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TeachScreen()))
                    : null,
              ),
              IconButton(
                tooltip: 'Settings',
                icon: const Icon(Icons.settings_outlined),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
              ),
            ],
          ),
          body: !s.api.configured
              ? _SetupPrompt()
              : RefreshIndicator(
                  onRefresh: s.refresh,
                  child: ListView(
                    padding: const EdgeInsets.only(bottom: 90),
                    children: [
                      if (s.snoozed) _SnoozeBanner(until: s.snoozedUntil!),
                      if (s.error != null)
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Text('Could not reach the server: ${s.error}', style: const TextStyle(color: C.rose)),
                        ),
                      if (s.calls.isEmpty && s.error == null)
                        const Padding(
                          padding: EdgeInsets.all(32),
                          child: Text(
                            'No calls yet. Screened calls will appear here.\n\nTap the flask icon to try a test call.',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: C.paperDim),
                          ),
                        ),
                      ..._sorted(s.calls).map((c) => _CallTile(call: c)),
                    ],
                  ),
                ),
          floatingActionButton: s.api.configured
              ? FloatingActionButton.extended(
                  backgroundColor: s.snoozed ? C.amber : C.teal,
                  foregroundColor: C.ink,
                  icon: Icon(s.snoozed ? Icons.play_arrow : Icons.snooze),
                  label: Text(s.snoozed ? 'Resume Chintan' : 'Snooze'),
                  onPressed: () => s.snoozed ? s.snooze(0) : _snoozeSheet(context),
                )
              : null,
        );
      },
    );
  }

  /// Live calls first, then regulatory and scam calls from today, then everything by time.
  List<Map<String, dynamic>> _sorted(List<Map<String, dynamic>> calls) {
    final list = [...calls];
    int rank(Map<String, dynamic> c) {
      if (c['status'] == 'live') return 0;
      final cat = (c['analysis'] as Map?)?['category'];
      final today = DateTime.now().difference(
              DateTime.fromMillisecondsSinceEpoch(((c['started_at'] as num) * 1000).round())) <
          const Duration(hours: 24);
      if (today && (cat == 'regulatory' || cat == 'spam_scam')) return 1;
      return 2;
    }

    list.sort((a, b) {
      final r = rank(a).compareTo(rank(b));
      return r != 0 ? r : (b['started_at'] as num).compareTo(a['started_at'] as num);
    });
    return list;
  }

  Future<void> _snoozeSheet(BuildContext context) async {
    final minutes = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: C.ink2,
      builder: (_) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const ListTile(title: Text('Snooze Chintan', style: TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text('Calls ring you normally until it switches back on by itself.')),
          for (final m in const [30, 60, 120, 240])
            ListTile(
              leading: const Icon(Icons.timer_outlined),
              title: Text(m < 60 ? '$m minutes' : '${m ~/ 60} hour${m > 60 ? 's' : ''}'),
              onTap: () => Navigator.pop(context, m),
            ),
        ]),
      ),
    );
    if (minutes != null) await appState.snooze(minutes);
  }

  Future<void> _startTestCall(BuildContext context) async {
    try {
      final r = await appState.api.post('/api/simulate', {}) as Map<String, dynamic>;
      if (!context.mounted) return;
      Navigator.push(context,
          MaterialPageRoute(builder: (_) => CallScreen(callId: r['call_id'] as String, simulator: true)));
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not start a test call: $e')));
      }
    }
  }
}

class _SetupPrompt extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ClipRRect(borderRadius: BorderRadius.circular(24), child: Image.asset('assets/icon.png', width: 120)),
          const SizedBox(height: 20),
          const Text('Chintan AI Call Assistant', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          const Text('Connect the app to your Chintan server to start.',
              textAlign: TextAlign.center, style: TextStyle(color: C.paperDim)),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            child: const Text('Connect server'),
          ),
        ]),
      ),
    );
  }
}

class _SnoozeBanner extends StatelessWidget {
  const _SnoozeBanner({required this.until});
  final DateTime until;

  @override
  Widget build(BuildContext context) {
    final t = '${until.hour.toString().padLeft(2, '0')}:${until.minute.toString().padLeft(2, '0')}';
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: C.amber.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        const Icon(Icons.snooze, color: C.amber),
        const SizedBox(width: 10),
        Expanded(child: Text('Chintan is snoozed until $t. Calls ring you directly.')),
      ]),
    );
  }
}

class _CallTile extends StatelessWidget {
  const _CallTile({required this.call});
  final Map<String, dynamic> call;

  @override
  Widget build(BuildContext context) {
    final a = Map<String, dynamic>.from((call['analysis'] as Map?) ?? {});
    final live = call['status'] == 'live';
    final cat = (a['display_category'] ?? a['category']) as String?;
    final name = (a['caller_name'] as String?) ?? (call['caller_number'] as String?) ??
        (call['source'] == 'simulator' ? 'Test call' : 'Unknown caller');
    final summary = (a['one_line_summary'] as String?) ?? '';
    final flag = a['deadline_flag'] as String?;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.push(
            context, MaterialPageRoute(builder: (_) => CallScreen(callId: call['id'] as String))),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              if (live) ...[
                const Icon(Icons.graphic_eq, color: C.teal, size: 18),
                const SizedBox(width: 6),
              ],
              Expanded(
                  child: Text(name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
                      overflow: TextOverflow.ellipsis)),
              Text(live ? 'LIVE' : formatTime(call['started_at'] as num?),
                  style: TextStyle(color: live ? C.teal : C.paperDim, fontSize: 12, fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 4, children: [
              if (cat != null) CategoryChip(appState.categoryLabel(cat), cat),
              if (flag == 'urgent' || flag == 'approaching')
                CategoryChip(a['days_to_deadline'] == 0 ? 'Due today' : '${a['days_to_deadline']}d to deadline',
                    flag == 'urgent' ? 'spam_scam' : 'bank'),
              if (call['outcome'] == 'joined') const CategoryChip('You joined', 'client_general'),
            ]),
            if (summary.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(summary, style: const TextStyle(color: C.paperDim), maxLines: 2, overflow: TextOverflow.ellipsis),
            ],
          ]),
        ),
      ),
    );
  }
}
