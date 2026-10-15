import 'package:flutter/material.dart';

import '../models.dart';
import '../theme.dart';
import '../widgets.dart';

const Color _kMuted = Color(0xFF68756D);

/// Compares 2–4 saved analyses.
///
/// The main content is a plain-language summary of what changed (soil
/// readings, recommended crop, yield, fertilizer advice, soil-adjustment
/// status). The raw field-by-field table stays underneath as supporting detail.
///
/// This is *not* crop-rotation analysis: "recommended crop" here is just the
/// model's suggestion for each saved analysis.
class CompareScreen extends StatelessWidget {
  const CompareScreen({super.key, required this.result});

  final CompareResult result;

  @override
  Widget build(BuildContext context) {
    final summary = result.summary;

    final children = <Widget>[];
    if (summary != null) {
      final overall = summary.overall;
      final stepCount = summary.steps.length;

      if (overall != null) {
        children.add(_StepView(
          step: overall,
          heading: 'Overall: first to last',
          fromCaption: 'First',
          toCaption: 'Last',
        ));
        children.add(const SizedBox(height: 24));
      }

      for (var i = 0; i < stepCount; i++) {
        children.add(_StepView(
          step: summary.steps[i],
          heading: stepCount == 1 ? 'What changed' : 'Step ${i + 1} of $stepCount',
          fromCaption: stepCount == 1 ? 'Previous' : 'Earlier',
          toCaption: stepCount == 1 ? 'Current' : 'Later',
        ));
        children.add(const SizedBox(height: 24));
      }
    }

    children.add(_DetailedComparison(
      result: result,
      // If the backend sent no summary, the table is all there is.
      initiallyExpanded: summary == null,
    ));

    return Scaffold(
      appBar: AppBar(title: const Text('Compare analyses')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: children,
      ),
    );
  }
}

// ── Summary ─────────────────────────────────────────────────────────────

class _StepView extends StatelessWidget {
  const _StepView({
    required this.step,
    required this.heading,
    required this.fromCaption,
    required this.toCaption,
  });

  final ChangeStep step;
  final String heading;
  final String fromCaption;
  final String toCaption;

  @override
  Widget build(BuildContext context) {
    final cropChange = step.cropChange;
    final yieldChange = step.yieldChange;

    final blocks = <Widget>[
      Text(
        heading,
        style: const TextStyle(
            fontSize: 18, fontWeight: FontWeight.w700, color: kDark),
      ),
      Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(child: _EntryChip(entry: step.fromEntry, caption: fromCaption)),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Icon(Icons.arrow_forward, size: 18, color: _kMuted),
          ),
          Expanded(child: _EntryChip(entry: step.toEntry, caption: toCaption)),
        ],
      ),
    ];

    if (cropChange != null || yieldChange != null) {
      blocks.add(Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (cropChange != null)
            Expanded(
              child: _MetricTile(
                label: 'Recommended crop',
                value: cropChange.changed
                    ? '${cropChange.before} → ${cropChange.after}'
                    : cropChange.after,
                note: cropChange.changed ? 'Changed' : 'No change',
                noteColor: cropChange.changed ? kClay : _kMuted,
              ),
            ),
          if (cropChange != null && yieldChange != null)
            const SizedBox(width: 10),
          if (yieldChange != null)
            Expanded(child: _yieldTile(yieldChange)),
        ],
      ));
    }

    blocks.add(SectionCard(
      title: 'Key changes',
      icon: Icons.checklist,
      child: step.keyChanges.isEmpty
          ? const Text(
              'No differences were found between these analyses.',
              style: TextStyle(color: _kMuted),
            )
          : Column(
              children: [
                for (final change in step.keyChanges) _ChangeRow(item: change),
              ],
            ),
    ));

    if (step.interpretation.isNotEmpty) {
      blocks.add(SectionCard(
        title: 'What this means',
        icon: Icons.lightbulb_outline,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final line in step.interpretation)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 6, right: 8),
                      child: Icon(Icons.circle, size: 5, color: kAccent),
                    ),
                    Expanded(
                      child: Text(line, style: const TextStyle(height: 1.35)),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ));
    }

    if (step.sections.isNotEmpty) {
      blocks.add(_Breakdown(sections: step.sections));
    }

    for (final note in step.notes) {
      blocks.add(Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 1, right: 6),
            child: Icon(Icons.info_outline, size: 14, color: _kMuted),
          ),
          Expanded(
            child: Text(
              note,
              style: const TextStyle(fontSize: 12, color: _kMuted, height: 1.35),
            ),
          ),
        ],
      ));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < blocks.length; i++) ...[
          if (i > 0) const SizedBox(height: 12),
          blocks[i],
        ],
      ],
    );
  }

  Widget _yieldTile(YieldChange change) {
    final color = _toneColor(change.tone, 'neutral');
    final String note;
    if (change.delta == 0) {
      note = 'No change';
    } else {
      final arrow = change.delta > 0 ? '▲' : '▼';
      final percent = change.percent;
      final percentText = percent == null
          ? ''
          : ' (${percent > 0 ? '+' : '−'}${_fmt(percent.abs())}%)';
      note = '$arrow ${_fmt(change.delta.abs())} kg/ha$percentText';
    }
    return _MetricTile(
      label: 'Predicted yield',
      value: '${_fmt(change.after)} kg/ha',
      note: note,
      noteColor: change.delta == 0 ? _kMuted : color,
    );
  }
}

class _EntryChip extends StatelessWidget {
  const _EntryChip({required this.entry, required this.caption});

  final EntryRef entry;
  final String caption;

  @override
  Widget build(BuildContext context) {
    final date = entry.createdAt;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: kBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(caption,
              style: const TextStyle(
                  fontSize: 10, letterSpacing: 0.5, color: _kMuted)),
          const SizedBox(height: 2),
          Text(
            entry.name,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          ),
          if (date != null)
            Text(kDateFormat.format(date),
                style: const TextStyle(fontSize: 11, color: _kMuted)),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    required this.note,
    required this.noteColor,
  });

  final String label;
  final String value;
  final String note;
  final Color noteColor;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12, color: _kMuted)),
            const SizedBox(height: 6),
            Text(
              value,
              style: const TextStyle(
                  fontSize: 17, fontWeight: FontWeight.w700, color: kDark),
            ),
            const SizedBox(height: 4),
            Text(
              note,
              style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600, color: noteColor),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChangeRow extends StatelessWidget {
  const _ChangeRow({required this.item});

  final ChangeItem item;

  @override
  Widget build(BuildContext context) {
    final isSame = item.direction == 'same';
    final color = _toneColor(item.tone, item.direction);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(_directionIcon(item.direction), size: 18, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              item.text,
              style: TextStyle(
                height: 1.35,
                color: isSame ? _kMuted : kDark,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Every detail line, grouped by topic and collapsed by default.
class _Breakdown extends StatelessWidget {
  const _Breakdown({required this.sections});

  final List<ChangeSection> sections;

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          leading: const Icon(Icons.unfold_more, size: 18, color: kAccent),
          title: const Text(
            'Full breakdown',
            style: TextStyle(
                fontWeight: FontWeight.w600, fontSize: 16, color: kDark),
          ),
          subtitle: const Text(
            'Every reading, crop, yield, fertilizer and soil-status line',
            style: TextStyle(fontSize: 12, color: _kMuted),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final section in sections) ...[
              Padding(
                padding: const EdgeInsets.only(top: 8, bottom: 2),
                child: Text(
                  section.title,
                  style: const TextStyle(
                      fontWeight: FontWeight.w600, color: kAccent),
                ),
              ),
              for (final item in section.items) _ChangeRow(item: item),
            ],
          ],
        ),
      ),
    );
  }
}

// ── Detailed field-by-field table (the original Compare view) ──────────

class _DetailedComparison extends StatelessWidget {
  const _DetailedComparison({
    required this.result,
    required this.initiallyExpanded,
  });

  final CompareResult result;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    final headers = result.entries
        .map((entry) => entry.label?.isNotEmpty == true
            ? entry.label!
            : entry.createdAt == null
                ? entry.chosenCrop
                : kDateFormat.format(entry.createdAt!))
        .toList();

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: initiallyExpanded,
          leading: const Icon(Icons.table_chart_outlined, size: 18, color: kAccent),
          title: const Text(
            'Detailed comparison',
            style: TextStyle(
                fontWeight: FontWeight.w600, fontSize: 16, color: kDark),
          ),
          subtitle: const Text(
            'Field-by-field values; rows that differ are highlighted',
            style: TextStyle(fontSize: 12, color: _kMuted),
          ),
          childrenPadding: const EdgeInsets.only(bottom: 8),
          children: [
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                headingRowColor:
                    WidgetStatePropertyAll(kAccent.withValues(alpha: 0.08)),
                columns: [
                  const DataColumn(label: Text('Field')),
                  for (final header in headers)
                    DataColumn(
                      label: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 140),
                        child: Text(header,
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                      ),
                    ),
                ],
                rows: [
                  for (final row in result.rows)
                    DataRow(
                      color: row.changed
                          ? WidgetStatePropertyAll(kWarn.withValues(alpha: 0.10))
                          : null,
                      cells: [
                        DataCell(Text(
                          row.unit.isEmpty ? row.field : '${row.field} (${row.unit})',
                          style: const TextStyle(fontWeight: FontWeight.w500),
                        )),
                        for (final value in row.values)
                          DataCell(ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 140),
                            child: Text(value, overflow: TextOverflow.ellipsis),
                          )),
                      ],
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── helpers ─────────────────────────────────────────────────────────────

IconData _directionIcon(String direction) {
  switch (direction) {
    case 'up':
      return Icons.arrow_upward;
    case 'down':
      return Icons.arrow_downward;
    case 'same':
      return Icons.remove;
    default:
      return Icons.swap_horiz;
  }
}

/// Green/red only where the analysis defines better/worse; otherwise neutral.
Color _toneColor(String tone, String direction) {
  if (direction == 'same') return _kMuted;
  switch (tone) {
    case 'positive':
      return kAccent;
    case 'negative':
      return kDanger;
    default:
      return kClay;
  }
}

/// Up to two decimals, trailing zeros dropped: 1515.40 -> "1515.4", 5.00 -> "5".
String _fmt(double value) =>
    value.toStringAsFixed(2).replaceFirst(RegExp(r'\.?0+$'), '');
