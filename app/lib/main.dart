import 'package:flutter/material.dart';

import 'screens/home.dart';
import 'state.dart';
import 'theme.dart';

final appState = AppState();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await appState.init();
  runApp(const ChintanApp());
}

class ChintanApp extends StatelessWidget {
  const ChintanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Chintan AI Call Assistant',
      debugShowCheckedModeBanner: false,
      theme: chintanTheme(),
      home: const HomeScreen(),
    );
  }
}
