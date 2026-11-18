import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';

/// "Teach Chintan how I talk": paste parts of your real calls so Chintan copies
/// your tone and Hindi/English mix. Numbers, PAN, Aadhaar, amounts and emails
/// are blanked out by the server before saving.
class TeachScreen extends StatefulWidget {
  const TeachScreen({super.key});

  @override
  State<TeachScreen> createState() => _TeachScreenState();
}

class _TeachScreenState extends State<TeachScreen> {
  List<Map<String, dynamic>>? _examples;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = await appState.api.get('/api/examples') as Map<String, dynamic>;
      setState(() => _examples = List<Map<String, dynamic>>.from(r['examples'] as List));
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _add() async {
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const _AddExample()));
    if (saved == true) _load();
  }

  Future<void> _delete(Map<String, dynamic> e) async {
    await appState.api.delete('/api/examples/${e['id']}');
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final list = _examples;
    return Scaffold(
      appBar: AppBar(title: const Text('Teach Chintan how I talk')),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: C.teal,
        foregroundColor: C.ink,
        onPressed: _add,
        icon: const Icon(Icons.add),
        label: const Text('Add a call'),
      ),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 100), children: [
        const Text(
          'Paste parts of your real phone calls. Chintan reads a few similar ones before every reply, '
          'so it sounds like you: your words, your tone, your Hindi-English mix.',
          style: TextStyle(color: C.paperDim),
        ),
        const SizedBox(height: 12),
        const _HowTo(),
        const SizedBox(height: 16),
        if (_error != null) Text(_error!, style: const TextStyle(color: C.rose)),
        if (list == null && _error == null) const Center(child: CircularProgressIndicator()),
        if (list != null && list.isEmpty)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Text('No calls added yet. Start with 3 to 5 typical calls: a bank RM, a client, a GST query.',
                textAlign: TextAlign.center, style: TextStyle(color: C.paperDim)),
          ),
        ...?list?.map((e) => Card(
              margin: const EdgeInsets.symmetric(vertical: 5),
              child: ListTile(
                title: Text(e['title'] as String, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(e['text'] as String, maxLines: 3, overflow: TextOverflow.ellipsis),
                trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(e)),
              ),
            )),
      ]),
    );
  }
}

class _HowTo extends StatelessWidget {
  const _HowTo();

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('How to get a call transcript on iPhone', style: TextStyle(fontWeight: FontWeight.w600)),
        children: const [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '1. During a call, tap the record button (top left) or More > Call Recording. '
              'Both sides hear that the call is being recorded.\n'
              '2. After the call, open Notes > Call Recordings > the call.\n'
              '3. Tap the transcript, select all, copy.\n'
              '4. Here, tap Add a call and paste.\n\n'
              'On Android, use your phone\'s built-in call recorder and its transcript, or type out the gist of a call.\n\n'
              'Numbers, PAN, Aadhaar, amounts and emails are blanked out automatically. '
              'Please delete client names yourself before saving.',
              style: TextStyle(color: C.paperDim, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

class _AddExample extends StatefulWidget {
  const _AddExample();

  @override
  State<_AddExample> createState() => _AddExampleState();
}

class _AddExampleState extends State<_AddExample> {
  final _title = TextEditingController();
  final _text = TextEditingController();
  bool _saving = false;

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await appState.api.post('/api/examples', {'title': _title.text, 'text': _text.text});
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add a call'), actions: [
        TextButton(onPressed: _saving ? null : _save, child: const Text('Save')),
      ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: _title,
          decoration: const InputDecoration(labelText: 'What kind of call?', hintText: 'e.g. Bank RM pitching a loan'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _text,
          maxLines: 16,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'Paste the transcript here.\n\nRemove client names first. Numbers, PAN, Aadhaar, '
                'amounts and emails are blanked out automatically.',
          ),
        ),
      ]),
    );
  }
}
