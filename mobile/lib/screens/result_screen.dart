import 'package:flutter/material.dart';

import '../models.dart';
import '../rotation_widgets.dart';
import '../theme.dart';
import '../widgets.dart';
import 'chat_screen.dart';

/// Full result of one pipeline run: crop recommendation, soil analysis,
/// fertilizer plan and yield prediction.
class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key, required this.result});

  final PredictionResult result;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(result.label?.isNotEmpty == true
            ? result.label!
            : 'Analysis — ${result.chosenCrop}'),
        actions: [
          IconButton(
            tooltip: 'Ask the assistant about this run',
            icon: const Icon(Icons.chat_bubble_outline),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => Scaffold(
                  appBar: AppBar(title: const Text('Assistant')),
                  body: ChatScreen(predictionId: result.id),
                ),
              ),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (result.createdAt != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(kDateFormat.format(result.createdAt!),
                  style: const TextStyle(color: Color(0xFF68756D), fontSize: 12)),
            ),
          _DecisionCard(result: result),
          if (result.cropMismatch)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFBF1D6),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: kWarn.withValues(alpha: 0.35)),
                ),
                child: Text(
                  'You targeted ${result.chosenCrop}, but the model ranks '
                  '${result.recommendedCrop} highest for this soil.',
                  style: const TextStyle(color: kWarn),
                ),
              ),
            ),
          // Record the crop actually grown -> drives the crop-rotation alerts
          // (website: "Save to field record" + the rotation banner under it).
          if (result.id != null) ...[
            const SizedBox(height: 16),
            GrownCropCard(
              entryId: result.id!,
              initialGrownCrop: result.grownCrop,
            ),
            const SizedBox(height: 12),
            RotationAlerts(field: result.label ?? ''),
          ],
          const SizedBox(height: 16),
          SectionCard(
            title: 'Crop recommendation',
            icon: Icons.grass,
            child: Column(
              children: [
                for (final crop in result.topCrops)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(crop.crop),
                            Text('${crop.percent.toStringAsFixed(1)}%',
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 4),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: LinearProgressIndicator(
                            value: crop.probability.clamp(0, 1),
                            minHeight: 8,
                            backgroundColor: kBorder,
                            color: kAccent,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Soil analysis vs. ideal for ${result.chosenCrop}',
            icon: Icons.water_drop_outlined,
            child: Column(
              children: [
                for (final nutrient in result.soilAnalysis)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      children: [
                        Expanded(flex: 3, child: Text(nutrient.nutrient)),
                        Expanded(
                          flex: 4,
                          child: Text(
                            '${nutrient.current.toStringAsFixed(1)} → ideal ${nutrient.ideal.toStringAsFixed(1)}',
                            style: const TextStyle(fontSize: 12, color: Color(0xFF68756D)),
                          ),
                        ),
                        Container(
                          padding:
                              const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: statusColor(nutrient.status).withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            nutrient.status,
                            style: TextStyle(
                                fontSize: 11,
                                color: statusColor(nutrient.status),
                                fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Fertilizer recommendation',
            icon: Icons.science_outlined,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (result.fertilizerRecs.isEmpty)
                  const Text('Soil is balanced — no correction needed.'),
                for (final rec in result.fertilizerRecs)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${rec.nutrient} ${rec.condition.toLowerCase()} → ${rec.fertilizer}'
                          '${rec.npkRatio.isEmpty || rec.npkRatio == '-' ? '' : ' (${rec.npkRatio})'}',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 2),
                        Text(rec.doseNote,
                            style: const TextStyle(fontSize: 12, color: Color(0xFF4D5D54))),
                        Text(rec.reason,
                            style: const TextStyle(fontSize: 11, color: Color(0xFF68756D))),
                      ],
                    ),
                  ),
                if (result.cropPrimaryFertilizer != null) ...[
                  const Divider(),
                  Text('Primary for ${result.chosenCrop}: ${result.cropPrimaryFertilizer}',
                      style: const TextStyle(fontSize: 12)),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Yield prediction',
            icon: Icons.trending_up,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(formatYield(result.predictedYieldKgHa),
                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(result.yieldInterpretation),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SectionCard(
            title: 'Inputs used',
            icon: Icons.list_alt,
            child: Wrap(
              spacing: 10,
              runSpacing: 6,
              children: [
                _chip('N', '${result.soilInput.nitrogen.toStringAsFixed(0)} kg/ha'),
                _chip('P', '${result.soilInput.phosphorus.toStringAsFixed(0)} kg/ha'),
                _chip('K', '${result.soilInput.potassium.toStringAsFixed(0)} kg/ha'),
                _chip('pH', result.soilInput.ph.toStringAsFixed(1)),
                _chip('Temp', '${result.soilInput.temperature.toStringAsFixed(1)} °C'),
                _chip('Rain', '${result.soilInput.rainfall.toStringAsFixed(0)} mm'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, String value) => Chip(
        backgroundColor: const Color(0xFFEEE8D9),
        side: const BorderSide(color: kBorder),
        label: Text('$label: $value', style: const TextStyle(fontSize: 12)),
      );
}


/// Forest-green "decision returned" card — the website's `.res-card`.
class _DecisionCard extends StatelessWidget {
  const _DecisionCard({required this.result});

  final PredictionResult result;

  static const Color _cream = Color(0xFFF2EFE6);

  @override
  Widget build(BuildContext context) {
    final imbalances =
        result.soilAnalysis.where((n) => n.status != 'Optimal').length;
    final soilHealth = result.soilAnalysis.isEmpty
        ? '—'
        : imbalances == 0
            ? 'All Optimal'
            : imbalances == 1
                ? '1 imbalance detected'
                : '$imbalances imbalances detected';
    final match = result.recommendedCropProbability;
    final soil = result.soilInput;

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: kAccent,
        borderRadius: BorderRadius.circular(20),
        boxShadow: kPaperShadow,
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'DECISION RETURNED · ${result.chosenCrop}'.toUpperCase(),
                        style: monoLabelStyle(color: kGold, size: 9.5),
                      ),
                    ),
                    Container(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: const Text('Predicted',
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                              color: _cream)),
                    ),
                  ],
                ),
                const SizedBox(height: 28),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Best fit for this soil',
                              style: TextStyle(
                                  fontSize: 12.5,
                                  color: _cream.withValues(alpha: 0.65))),
                          const SizedBox(height: 4),
                          Text(
                            result.recommendedCrop ?? '—',
                            style: displayStyle(
                                size: 40,
                                weight: FontWeight.w500,
                                color: kGold,
                                height: 1.05),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Predicted ${formatYield(result.predictedYieldKgHa)} '
                            'for ${result.chosenCrop}',
                            style: TextStyle(
                                fontSize: 13,
                                height: 1.4,
                                color: _cream.withValues(alpha: 0.75)),
                          ),
                        ],
                      ),
                    ),
                    if (match != null)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text.rich(
                            TextSpan(
                              children: [
                                TextSpan(
                                  text: (match * 100).toStringAsFixed(0),
                                  style: const TextStyle(
                                      fontSize: 42,
                                      fontWeight: FontWeight.w800,
                                      letterSpacing: -1,
                                      color: _cream),
                                ),
                                const TextSpan(
                                  text: '%',
                                  style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                      color: _cream),
                                ),
                              ],
                            ),
                          ),
                          Text('MATCH SCORE',
                              style: monoLabelStyle(
                                  color: _cream.withValues(alpha: 0.6),
                                  size: 8.5)),
                        ],
                      ),
                  ],
                ),
              ],
            ),
          ),
          Container(
            color: Colors.white.withValues(alpha: 0.14),
            child: Column(
              children: [
                Row(
                  children: [
                    _cell('Soil pH', soil.ph.toStringAsFixed(1)),
                    const SizedBox(width: 1),
                    _cell('Rainfall', '${soil.rainfall.toStringAsFixed(0)} mm'),
                  ],
                ),
                const SizedBox(height: 1),
                Row(
                  children: [
                    _cell('Temperature',
                        '${soil.temperature.toStringAsFixed(1)}°C'),
                    const SizedBox(width: 1),
                    _cell('Soil health', soilHealth),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _cell(String label, String value) => Expanded(
        child: Container(
          color: kAccent,
          padding: const EdgeInsets.fromLTRB(22, 14, 12, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label.toUpperCase(),
                  style: monoLabelStyle(
                      color: _cream.withValues(alpha: 0.6), size: 8.5)),
              const SizedBox(height: 4),
              Text(value,
                  style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: _cream)),
            ],
          ),
        ),
      );
}
