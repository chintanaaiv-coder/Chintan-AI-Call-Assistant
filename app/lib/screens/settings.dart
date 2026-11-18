import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../main.dart';
import '../native.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _url = TextEditingController(text: appState.api.baseUrl);
  late final _token = TextEditingController(text: appState.api.token);
  late final _instructions = TextEditingController(text: (appState.settings['standing_instructions'] as String?) ?? '');
  late final _quick = TextEditingController(text: appState.quickReplies.join('\n'));
  final _forwardTo = TextEditingController();
  String? _status;
  bool? _hasRole;

  @override
  void initState() {
    super.initState();
    NativeScreening.hasRole().then((v) {
      if (mounted) setState(() => _hasRole = v);
    });
  }

  Future<void> _connect() async {
    setState(() => _status = 'Checking...');
    try {
      await appState.saveServer(_url.text, _token.text);
      final h = await appState.api.health();
      final problems = List<String>.from((h['problems'] as List?) ?? const []);
      setState(() => _status = appState.error != null
          ? 'Could not log in: ${appState.error}'
          : problems.isEmpty
              ? 'Connected. Everything is set up.'
              : 'Connected. Still to do on the server:\n- ${problems.join('\n- ')}');
      _instructions.text = (appState.settings['standing_instructions'] as String?) ?? '';
      _quick.text = appState.quickReplies.join('\n');
    } catch (e) {
      setState(() => _status = 'Could not reach the server: $e');
    }
  }

  Future<void> _saveRules() async {
    await appState.saveSettings({
      'standing_instructions': _instructions.text,
      'quick_replies': _quick.text.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
    });
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved')));
  }

  /// Opens the phone dialer with a carrier code (works on Jio, Airtel, Vi and BSNL).
  Future<void> _dial(String code) async {
    await launchUrl(Uri.parse('tel:${Uri.encodeComponent(code)}'));
  }

  @override
  Widget build(BuildContext context) {
    final number = _forwardTo.text.replaceAll(RegExp(r'[^\d+]'), '');
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListenableBuilder(
        listenable: appState,
        builder: (context, _) => ListView(padding: const EdgeInsets.all(16), children: [
          _h('Server'),
          TextField(controller: _url, decoration: const InputDecoration(labelText: 'Server address', hintText: 'https://chintan-server.onrender.com')),
          TextField(controller: _token, obscureText: true, decoration: const InputDecoration(labelText: 'App token (APP_TOKEN)')),
          const SizedBox(height: 10),
          FilledButton(onPressed: _connect, child: const Text('Save and connect')),
          if (_status != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_status!)),

          if (NativeScreening.supported) ...[
            _h('Call screening on this phone'),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(_hasRole == true ? Icons.verified : Icons.warning_amber, color: _hasRole == true ? C.teal : C.amber),
              title: Text(_hasRole == true ? 'Chintan is your call-screening app' : 'Chintan is not screening calls yet'),
              trailing: _hasRole == true
                  ? null
                  : TextButton(
                      onPressed: () async {
                        final ok = await NativeScreening.requestRole();
                        setState(() => _hasRole = ok);
                      },
                      child: const Text('Allow')),
            ),
            DropdownButtonFormField<String>(
              initialValue: appState.screeningMode,
              decoration: const InputDecoration(labelText: 'Which calls go to Chintan'),
              items: const [
                DropdownMenuItem(value: 'all', child: Text('All calls, saved contacts too')),
                DropdownMenuItem(value: 'unknown', child: Text('Only numbers not in my contacts')),
                DropdownMenuItem(value: 'off', child: Text('Off - ring me for everything')),
              ],
              onChanged: (v) => appState.setScreeningMode(v ?? 'all'),
            ),
          ],

          _h('Call forwarding (one-time setup)'),
          const Text(
            'Calls Chintan screens are sent by your mobile network to your Chintan (Exotel) number. '
            'Enter that number, then tap each button and press call. You will hear or see a confirmation from your network.',
            style: TextStyle(color: C.paperDim),
          ),
          TextField(
            controller: _forwardTo,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(labelText: 'Your Chintan (Exotel) number', hintText: '0XXXXXXXXXX'),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton(
                onPressed: number.isEmpty ? null : () => _dial('**67*$number#'),
                child: const Text('When busy / declined')),
            OutlinedButton(
                onPressed: number.isEmpty ? null : () => _dial('**61*$number#'),
                child: const Text('When not answered')),
            OutlinedButton(
                onPressed: number.isEmpty ? null : () => _dial('**62*$number#'),
                child: const Text('When switched off')),
            TextButton(onPressed: () => _dial('##002#'), child: const Text('Turn all forwarding off')),
          ]),
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('On iPhone: set up the same codes, then decline a call to send it to Chintan.',
                style: TextStyle(color: C.paperDim, fontSize: 12)),
          ),

          if (appState.api.configured) ...[
            _h('Tell Chintan'),
            TextField(
              controller: _instructions,
              maxLines: 4,
              decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Plain-English rules for every call, e.g. "Ask GST callers for the DIN."'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _quick,
              maxLines: 5,
              decoration: const InputDecoration(
                  border: OutlineInputBorder(), labelText: 'Quick replies during a call (one per line)'),
            ),
            const SizedBox(height: 8),
            FilledButton.tonal(onPressed: _saveRules, child: const Text('Save')),
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text('Your rules never override the safety rules: no OTPs, PINs, PAN, Aadhaar, figures or client data to anyone.',
                  style: TextStyle(color: C.paperDim, fontSize: 12)),
            ),
            _h('Muted callers'),
            ...List<String>.from((appState.settings['muted'] as List?) ?? const []).map((n) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(n),
                  trailing: TextButton(onPressed: () => appState.unmute(n), child: const Text('Unmute')),
                )),
            if (((appState.settings['muted'] as List?) ?? const []).isEmpty)
              const Text('None', style: TextStyle(color: C.paperDim)),
          ],
          const SizedBox(height: 40),
        ]),
      ),
    );
  }

  Widget _h(String text) => Padding(
        padding: const EdgeInsets.only(top: 26, bottom: 6),
        child: Text(text, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: C.teal)),
      );
}
