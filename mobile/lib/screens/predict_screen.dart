import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets.dart';
import 'result_screen.dart';

class PredictScreen extends StatefulWidget {
  const PredictScreen({super.key});

  @override
  State<PredictScreen> createState() => _PredictScreenState();
}

class _PredictScreenState extends State<PredictScreen> {
  double _nitrogen = 58;
  double _phosphorus = 43;
  double _potassium = 37;
  double _ph = 6.4;
  double _temperature = 26.5;
  double _rainfall = 820;

  final _label = TextEditingController();
  String? _crop;
  List<String> _crops = const [];
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadCrops();
  }

  @override
  void dispose() {
    _label.dispose();
    super.dispose();
  }

  Future<void> _loadCrops() async {
    try {
      final crops = await context.read<AppState>().api.crops();
      if (mounted) setState(() => _crops = crops);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  Future<void> _run() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    final state = context.read<AppState>();
    try {
      final result = await state.api.predict(
        soil: SoilInput(
          nitrogen: _nitrogen,
          phosphorus: _phosphorus,
          potassium: _potassium,
          ph: _ph,
          temperature: _temperature,
          rainfall: _rainfall,
        ),
        crop: _crop,
        label: _label.text.trim(),
      );
      state.setLatestPrediction(result);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => ResultScreen(result: result)),
      );
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _slider({
    required String label,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String unit,
    required int decimals,
    required ValueChanged<double> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
            Text('${value.toStringAsFixed(decimals)} $unit',
                style: const TextStyle(color: kAccent, fontWeight: FontWeight.w600)),
          ],
        ),
        Slider(
          value: value,
          min: min,
          max: max,
          divisions: divisions,
          activeColor: kAccent,
          onChanged: _busy ? null : onChanged,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_error != null) ...[
          ErrorBanner(message: _error!),
          const SizedBox(height: 16),
        ],
        SectionCard(
          title: 'Crop decision desk',
          icon: Icons.tune,
          tag: 'Live workflow',
          subtitle: 'Authority starts with the field sample — enter your readings '
              'below for a crop recommendation, soil check, fertilizer plan and '
              'yield estimate.',
          child: Column(
            children: [
              _slider(
                label: 'Nitrogen (N)',
                value: _nitrogen,
                min: 0,
                max: 150,
                divisions: 150,
                unit: 'kg/ha',
                decimals: 0,
                onChanged: (value) => setState(() => _nitrogen = value),
              ),
              _slider(
                label: 'Phosphorus (P)',
                value: _phosphorus,
                min: 0,
                max: 150,
                divisions: 150,
                unit: 'kg/ha',
                decimals: 0,
                onChanged: (value) => setState(() => _phosphorus = value),
              ),
              _slider(
                label: 'Potassium (K)',
                value: _potassium,
                min: 0,
                max: 150,
                divisions: 150,
                unit: 'kg/ha',
                decimals: 0,
                onChanged: (value) => setState(() => _potassium = value),
              ),
              _slider(
                label: 'Soil pH',
                value: _ph,
                min: 4,
                max: 9,
                divisions: 50,
                unit: '',
                decimals: 1,
                onChanged: (value) => setState(() => _ph = value),
              ),
              _slider(
                label: 'Temperature',
                value: _temperature,
                min: 5,
                max: 50,
                divisions: 90,
                unit: '°C',
                decimals: 1,
                onChanged: (value) => setState(() => _temperature = value),
              ),
              _slider(
                label: 'Rainfall',
                value: _rainfall,
                min: 0,
                max: 2000,
                divisions: 200,
                unit: 'mm',
                decimals: 0,
                onChanged: (value) => setState(() => _rainfall = value),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        SectionCard(
          title: 'Analysis options',
          icon: Icons.grass,
          child: Column(
            children: [
              DropdownButtonFormField<String?>(
                initialValue: _crop,
                decoration: const InputDecoration(
                    labelText: 'Target crop (fertilizer & yield)'),
                items: [
                  const DropdownMenuItem<String?>(
                    value: null,
                    child: Text('Auto — use top recommendation'),
                  ),
                  for (final crop in _crops)
                    DropdownMenuItem<String?>(value: crop, child: Text(crop)),
                ],
                onChanged: _busy ? null : (value) => setState(() => _crop = value),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _label,
                decoration: const InputDecoration(
                  labelText: 'Label (optional)',
                  hintText: 'e.g. North field — June',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: _busy ? null : _run,
          icon: _busy
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.play_arrow),
          label: Text(_busy ? 'Running pipeline…' : 'Run analysis  →'),
        ),
        const SizedBox(height: 8),
        const Text(
          'Each run is saved to your private history. Record the crop you '
          'finally grew on the result screen to get crop-rotation alerts.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 11, color: Color(0xFF68756D)),
        ),
      ],
    );
  }
}
