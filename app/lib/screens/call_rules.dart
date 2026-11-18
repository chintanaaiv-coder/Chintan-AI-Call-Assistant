import 'package:flutter/material.dart';

import '../main.dart';
import '../theme.dart';

/// "How Chintan handles each type of call": the preloaded replies per call type
/// (bank pitch, client list request, sales, client deadline, GST office,
/// delivery...). Tap one to edit, swipe or tap the bin to remove, + to add.
class CallRulesScreen extends StatefulWidget {
  const CallRulesScreen({super.key});

  @override
  State<CallRulesScreen> createState() => _CallRulesScreenState();
}

class _CallRulesScreenState extends State<CallRulesScreen> {
  late List<Map<String, String>> _rules = _fromSettings();
  bool _dirty = false;

  List<Map<String, String>> _fromSettings() => ((appState.settings['category_rules'] as List?) ?? const [])
      .map((r) => {'category': '${(r as Map)['category']}', 'text': '${r['text']}'})
      .toList();

  Future<void> _edit({int? index}) async {
    final existing = index == null ? null : _rules[index];
    final keys = appState.categories.keys.toList();
    String category = existing?['category'] ?? (keys.isNotEmpty ? keys.first : 'unclear');
    final text = TextEditingController(text: existing?['text'] ?? '');
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          backgroundColor: C.ink2,
          title: Text(index == null ? 'New rule' : 'Edit rule'),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              DropdownButton<String>(
                isExpanded: true,
                value: keys.contains(category) ? category : null,
                hint: Text(appState.categoryLabel(category)),
                items: [for (final k in keys) DropdownMenuItem(value: k, child: Text(appState.categoryLabel(k)))],
                onChanged: (v) => setD(() => category = v ?? category),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: text,
                maxLines: 5,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'What Chintan should do or say for this type of call',
                ),
              ),
            ]),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, {'category': category, 'text': text.text.trim()}),
              child: const Text('OK'),
            ),
          ],
        ),
      ),
    );
    if (result == null || result['text']!.isEmpty) return;
    setState(() {
      if (index == null) {
        _rules.add(result);
      } else {
        _rules[index] = result;
      }
      _dirty = true;
    });
  }

  Future<void> _save() async {
    try {
      await appState.saveSettings({'category_rules': _rules});
      setState(() {
        _rules = _fromSettings();
        _dirty = false;
      });
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not save: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Replies by call type'),
        actions: [TextButton(onPressed: _dirty ? _save : null, child: const Text('Save'))],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: C.teal,
        foregroundColor: C.ink,
        onPressed: () => _edit(),
        child: const Icon(Icons.add),
      ),
      body: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 100), children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 0, 4, 12),
          child: Text(
            'How Chintan handles each kind of call. These came from your original call screener; '
            'tap one to change it. The safety rules (no OTPs, PAN, figures or client data) always apply on top.',
            style: TextStyle(color: C.paperDim),
          ),
        ),
        if (_rules.isEmpty)
          const Padding(
            padding: EdgeInsets.all(24),
            child: Text('No rules. Tap + to add one.', textAlign: TextAlign.center, style: TextStyle(color: C.paperDim)),
          ),
        for (var i = 0; i < _rules.length; i++)
          Card(
            margin: const EdgeInsets.symmetric(vertical: 5),
            child: ListTile(
              onTap: () => _edit(index: i),
              title: Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: CategoryChip(appState.categoryLabel(_rules[i]['category']), _rules[i]['category']),
                ),
              ),
              subtitle: Text(_rules[i]['text']!),
              trailing: IconButton(
                icon: const Icon(Icons.delete_outline),
                onPressed: () => setState(() {
                  _rules.removeAt(i);
                  _dirty = true;
                }),
              ),
            ),
          ),
      ]),
    );
  }
}
