import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:url_launcher/url_launcher.dart';

import '../main.dart';
import '../theme.dart';

/// One call. While it is live: the transcript as it happens, quick replies, a
/// message box, Join and End. Afterwards: summary, recording, transcript and
/// the next-step buttons (call back, WhatsApp, mute, delete).
class CallScreen extends StatefulWidget {
  const CallScreen({super.key, required this.callId, this.simulator = false});
  final String callId;
  final bool simulator;

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  Map<String, dynamic>? call;
  String? error;
  final _msg = TextEditingController();
  final _callerLine = TextEditingController();
  final _scroll = ScrollController();
  bool _simBusy = false;
  int _seenLive = 0;

  @override
  void initState() {
    super.initState();
    _load();
    appState.addListener(_onState);
  }

  @override
  void dispose() {
    appState.removeListener(_onState);
    _msg.dispose();
    _callerLine.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final c = await appState.api.get('/api/calls/${widget.callId}') as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        call = c;
        _seenLive = (appState.liveTurns[widget.callId] ?? const []).length;
      });
      _toBottom();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  void _onState() {
    if (call == null || !mounted) return;
    final live = appState.liveTurns[widget.callId] ?? const [];
    final summary = appState.calls.where((c) => c['id'] == widget.callId).toList();
    setState(() {
      if (live.length > _seenLive) {
        (call!['turns'] as List).addAll(live.sublist(_seenLive));
        _seenLive = live.length;
        _toBottom();
      }
      if (summary.isNotEmpty) {
        call!['analysis'] = summary.first['analysis'];
        call!['status'] = summary.first['status'];
        call!['outcome'] = summary.first['outcome'];
        call!['has_recording'] = summary.first['has_recording'];
        call!['live'] = summary.first['status'] == 'live';
      }
    });
  }

  void _toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  bool get _live => call?['live'] == true || call?['status'] == 'live';

  Map<String, dynamic> get _a => Map<String, dynamic>.from((call?['analysis'] as Map?) ?? {});

  String? get _number => call?['caller_number'] as String?;

  // --- live controls ---
  void _send(String text) {
    if (text.trim().isEmpty) return;
    appState.sendLive('say', widget.callId, text.trim());
    _msg.clear();
  }

  Future<void> _simulateCaller() async {
    final text = _callerLine.text.trim();
    if (text.isEmpty) return;
    setState(() => _simBusy = true);
    _callerLine.clear();
    try {
      await appState.api.post('/api/simulate/${widget.callId}', {'text': text});
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
    if (mounted) setState(() => _simBusy = false);
  }

  // --- after-call actions ---
  Future<void> _callBack() async {
    if (_number == null) return;
    await launchUrl(Uri(scheme: 'tel', path: _number));
  }

  Future<void> _whatsApp() async {
    final digits = (_number ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.length < 10) return;
    final intl = digits.length == 10 ? '91$digits' : digits.replaceFirst(RegExp(r'^0+'), '');
    final summary = (_a['one_line_summary'] as String?) ?? '';
    final draft = TextEditingController(
        text: 'Hello, this is ${appState.settings['owner_name'] ?? 'Chintan'}. '
            'Returning your call${summary.isNotEmpty ? ' regarding: $summary' : ''}.');
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: C.ink2,
        title: const Text('WhatsApp message'),
        content: TextField(controller: draft, maxLines: 5, decoration: const InputDecoration(border: OutlineInputBorder())),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, draft.text), child: const Text('Open WhatsApp')),
        ],
      ),
    );
    if (text == null) return;
    await launchUrl(Uri.parse('https://wa.me/$intl?text=${Uri.encodeComponent(text)}'),
        mode: LaunchMode.externalApplication);
  }

  Future<void> _mute() async {
    if (_number == null) return;
    await appState.mute(_number!);
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$_number muted. Chintan will politely decline their calls.')));
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: C.ink2,
        title: const Text('Delete this call?'),
        content: const Text('The transcript and recording will be deleted from the server.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true) {
      await appState.deleteCall(widget.callId);
      if (mounted) Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _a;
    final name = (a['caller_name'] as String?) ?? _number ?? (widget.simulator ? 'Test call' : 'Unknown caller');
    return Scaffold(
      appBar: AppBar(
        title: Text(name),
        actions: [if (!_live && call != null) IconButton(icon: const Icon(Icons.delete_outline), onPressed: _delete)],
      ),
      body: call == null
          ? Center(child: error != null ? Text(error!, style: const TextStyle(color: C.rose)) : const CircularProgressIndicator())
          : Column(children: [
              Expanded(
                child: ListView(controller: _scroll, padding: const EdgeInsets.all(12), children: [
                  _SummaryCard(analysis: a, live: _live, outcome: call!['outcome'] as String?),
                  if (!_live && call!['has_recording'] == true) _RecordingPlayer(url: appState.api.recordingUrl(widget.callId)),
                  if (!_live && _number != null) _actions(),
                  const SizedBox(height: 8),
                  ...((call!['turns'] as List).map((t) => _Bubble(turn: Map<String, dynamic>.from(t as Map)))),
                ]),
              ),
              if (_live) _liveControls(),
            ]),
    );
  }

  Widget _actions() => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(onPressed: _callBack, icon: const Icon(Icons.call), label: const Text('Call back')),
          FilledButton.tonalIcon(onPressed: _whatsApp, icon: const Icon(Icons.chat), label: const Text('WhatsApp')),
          OutlinedButton.icon(onPressed: _mute, icon: const Icon(Icons.volume_off), label: const Text('Mute caller')),
        ]),
      );

  Widget _liveControls() {
    return SafeArea(
      top: false,
      child: Container(
        color: C.ink2,
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (widget.simulator)
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _callerLine,
                  enabled: !_simBusy,
                  decoration: const InputDecoration(
                      hintText: 'Type what the CALLER says...', isDense: true, border: OutlineInputBorder()),
                  onSubmitted: (_) => _simulateCaller(),
                ),
              ),
              IconButton(
                  onPressed: _simBusy ? null : _simulateCaller,
                  icon: _simBusy
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.record_voice_over)),
            ]),
          SizedBox(
            height: 40,
            child: ListView(scrollDirection: Axis.horizontal, children: [
              for (final q in appState.quickReplies)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ActionChip(label: Text(q), onPressed: () => _send(q)),
                ),
            ]),
          ),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _msg,
                decoration: const InputDecoration(
                    hintText: 'Message for Chintan to say...', isDense: true, border: OutlineInputBorder()),
                onSubmitted: _send,
              ),
            ),
            IconButton(onPressed: () => _send(_msg.text), icon: const Icon(Icons.send)),
          ]),
          const SizedBox(height: 6),
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: C.teal),
                onPressed: () => appState.sendLive('join', widget.callId),
                icon: const Icon(Icons.call),
                label: const Text('Join call'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => appState.sendLive('end', widget.callId),
                icon: const Icon(Icons.call_end),
                label: const Text('Wrap up'),
              ),
            ),
          ]),
        ]),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.analysis, required this.live, this.outcome});
  final Map<String, dynamic> analysis;
  final bool live;
  final String? outcome;

  @override
  Widget build(BuildContext context) {
    final a = analysis;
    final cat = (a['display_category'] ?? a['category']) as String?;
    Widget row(String label, Object? value) => value == null || '$value'.isEmpty
        ? const SizedBox.shrink()
        : Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(width: 120, child: Text(label, style: const TextStyle(color: C.paperDim, fontSize: 13))),
              Expanded(child: Text('$value', style: const TextStyle(fontSize: 13))),
            ]),
          );
    const outcomes = {
      'message_taken': 'Message taken',
      'joined': 'You joined',
      'caller_hung_up': 'Caller hung up',
      'muted': 'Muted caller, declined',
      'snoozed': 'Put through (snoozed)',
    };
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            if (live) ...[const Icon(Icons.graphic_eq, color: C.teal), const SizedBox(width: 6)],
            Text(live ? 'Chintan is on the call' : (outcomes[outcome] ?? 'Call ended'),
                style: TextStyle(color: live ? C.teal : C.paperDim, fontWeight: FontWeight.w600)),
            const Spacer(),
            if (cat != null) CategoryChip(appState.categoryLabel(cat), cat),
          ]),
          if ((a['one_line_summary'] as String?)?.isNotEmpty == true) ...[
            const SizedBox(height: 10),
            Text(a['one_line_summary'] as String, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ],
          row('Details', a['key_details']),
          row('Client mentioned', a['matched_client_name']),
          row('Notice / ref no.', a['notice_or_reference_number']),
          row('Claims to be', a['claimed_authority']),
          row('Regulatory body', a['regulatory_body']),
          row('Deadline', a['deadline_label'] == null
              ? null
              : '${a['deadline_label']}${a['days_to_deadline'] != null ? ' - ${a['days_to_deadline']} days left' : ''}'),
          if (a['claimed_authority'] != null)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Verify this claim through official channels before sharing anything.',
                  style: TextStyle(color: C.rose, fontSize: 12)),
            ),
        ]),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.turn});
  final Map<String, dynamic> turn;

  @override
  Widget build(BuildContext context) {
    final speaker = turn['speaker'] as String;
    final mine = speaker != 'caller';
    final label = {'assistant': 'Chintan AI', 'caller': 'Caller', 'owner_message': 'You (via Chintan)'}[speaker] ?? speaker;
    final color = speaker == 'caller' ? C.ink2 : speaker == 'owner_message' ? C.amber.withValues(alpha: 0.25) : C.teal.withValues(alpha: 0.25);
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(fontSize: 11, color: C.paperDim, fontWeight: FontWeight.w600)),
          const SizedBox(height: 3),
          Text(turn['text'] as String),
        ]),
      ),
    );
  }
}

class _RecordingPlayer extends StatefulWidget {
  const _RecordingPlayer({required this.url});
  final String url;

  @override
  State<_RecordingPlayer> createState() => _RecordingPlayerState();
}

class _RecordingPlayerState extends State<_RecordingPlayer> {
  final _player = AudioPlayer();
  bool _loaded = false;
  String? _error;

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    try {
      if (!_loaded) {
        await _player.setUrl(widget.url);
        _loaded = true;
      }
      _player.playing ? await _player.pause() : await _player.play();
    } catch (e) {
      setState(() => _error = 'Could not play the recording');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(top: 8),
      child: StreamBuilder<PlayerState>(
        stream: _player.playerStateStream,
        builder: (context, snap) {
          final playing = snap.data?.playing ?? false;
          return ListTile(
            leading: IconButton(icon: Icon(playing ? Icons.pause_circle : Icons.play_circle, size: 36), onPressed: _toggle),
            title: const Text('Call recording'),
            subtitle: StreamBuilder<Duration>(
              stream: _player.positionStream,
              builder: (context, pos) {
                if (_error != null) return Text(_error!, style: const TextStyle(color: C.rose));
                final p = pos.data ?? Duration.zero;
                final d = _player.duration;
                String f(Duration x) => '${x.inMinutes}:${(x.inSeconds % 60).toString().padLeft(2, '0')}';
                return Text(d == null ? 'Caller and Chintan AI, both voices' : '${f(p)} / ${f(d)}');
              },
            ),
          );
        },
      ),
    );
  }
}
