/// Crop-rotation warnings — the mobile counterpart of the website's
/// "Crop rotation alert" cards and its "Save to field record" form.
///
/// No rotation rules live here: the advice is computed by the backend
/// (`GET /api/history/rotation`), which runs the same `history_store`
/// logic as the website, and only for the signed-in user's own runs.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api_client.dart';
import 'app_state.dart';
import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

/// One rotation warning card (website: `.rot-card`).
class RotationBanner extends StatelessWidget {
  const RotationBanner({super.key, required this.advice});

  final RotationAdvice advice;

  @override
  Widget build(BuildContext context) {
    final alert = advice.isAlert;
    final iconColor = alert ? kDanger : kWarn;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      decoration: BoxDecoration(
        color: alert ? const Color(0xFFF8E6E3) : const Color(0xFFFBF1D6),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: alert ? const Color(0xFFE6BDB6) : const Color(0xFFE6D3A0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.autorenew, size: 18, color: iconColor),
              const SizedBox(width: 10),
              const Text(
                'Crop rotation alert',
                style: TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 14, color: kDark),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            advice.headline,
            style: const TextStyle(
                fontWeight: FontWeight.w800, fontSize: 15, color: kDark),
          ),
          const SizedBox(height: 2),
          Text(
            advice.reason,
            style: const TextStyle(fontSize: 13, height: 1.45, color: kMid),
          ),
          if (advice.suggest.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text('CONSIDER NEXT SEASON', style: monoLabelStyle(size: 9.5)),
                for (final crop in advice.suggest)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                    decoration: BoxDecoration(
                      color: kAccent,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      crop,
                      style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: kBackground),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Loads the signed-in user's rotation warnings and shows one card per field.
///
/// Reloads whenever [AppState.historyRevision] changes (new run, grown crop
/// recorded, run deleted), so the cards never show stale advice. Failures are
/// swallowed on purpose — a notification area must never break the screen it
/// sits on.
class RotationAlerts extends StatefulWidget {
  const RotationAlerts({super.key, this.field, this.showHealthyNote = false});

  /// When set, only the warning for this field/label is shown ('' = unlabeled
  /// runs). When null, every field's warning is shown.
  final String? field;

  /// Show the website's "looks healthy" line when there is nothing to warn about.
  final bool showHealthyNote;

  @override
  State<RotationAlerts> createState() => _RotationAlertsState();
}

class _RotationAlertsState extends State<RotationAlerts> {
  List<RotationAdvice> _alerts = const [];
  bool _loaded = false;
  int _loadedRevision = -1;
  int _sequence = 0;

  Future<void> _load() async {
    final sequence = ++_sequence;
    final request = context.read<AppState>().api.rotationAlerts();
    try {
      final alerts = await request;
      if (!mounted || sequence != _sequence) return;
      setState(() {
        _alerts = alerts;
        _loaded = true;
      });
    } catch (_) {
      if (!mounted || sequence != _sequence) return;
      setState(() {
        _alerts = const [];
        _loaded = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final revision = context.watch<AppState>().historyRevision;
    if (revision != _loadedRevision) {
      _loadedRevision = revision;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _load();
      });
    }

    final field = widget.field;
    final shown = field == null
        ? _alerts
        : _alerts.where((a) => a.field.trim() == field.trim()).toList();

    if (shown.isEmpty) {
      if (widget.showHealthyNote && _loaded) {
        return const Padding(
          padding: EdgeInsets.only(bottom: 4),
          child: Text(
            '✅ No repeated crops detected — the rotation across your runs looks healthy.',
            style: TextStyle(fontSize: 12.5, color: kSoft),
          ),
        );
      }
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final advice in shown)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: RotationBanner(advice: advice),
          ),
      ],
    );
  }
}

/// "Crop you finally grew" form for one saved run (website: "Save to field
/// record"). Rotation alerts are based on this, so the dashboard, history and
/// result screens refresh as soon as it is saved.
class GrownCropCard extends StatefulWidget {
  const GrownCropCard({
    super.key,
    required this.entryId,
    this.initialGrownCrop,
  });

  final int entryId;
  final String? initialGrownCrop;

  @override
  State<GrownCropCard> createState() => _GrownCropCardState();
}

class _GrownCropCardState extends State<GrownCropCard> {
  List<String> _crops = const [];
  String? _selected;
  String? _saved;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _saved = widget.initialGrownCrop;
    _selected = widget.initialGrownCrop;
    _loadCrops();
  }

  Future<void> _loadCrops() async {
    try {
      final crops = await context.read<AppState>().api.crops();
      if (mounted) setState(() => _crops = crops);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  Future<void> _save() async {
    final crop = _selected;
    if (crop == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final state = context.read<AppState>();
    try {
      await state.api.setGrownCrop(widget.entryId, crop);
      if (!mounted) return;
      setState(() => _saved = crop);
      state.bumpHistory(); // refresh rotation alerts everywhere
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Save to field record',
      tag: 'Field record',
      icon: Icons.bookmark_border,
      subtitle: 'Tell us which crop you finally grew. Rotation alerts are '
          'based on what was actually grown, so this is required.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null) ...[
            ErrorBanner(message: _error!),
            const SizedBox(height: 12),
          ],
          if (_saved != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: kAccent.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_outline,
                      size: 18, color: kAccent),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('Saved — $_saved recorded for this run.',
                        style: const TextStyle(color: kAccent)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],
          DropdownButtonFormField<String>(
            // Rebuild once the crop list arrives so a preselected crop shows.
            key: ValueKey(_crops.length),
            initialValue: _crops.contains(_selected) ? _selected : null,
            decoration:
                const InputDecoration(labelText: 'Crop you finally grew *'),
            hint: const Text('Select the crop you grew'),
            items: [
              for (final crop in _crops)
                DropdownMenuItem<String>(value: crop, child: Text(crop)),
            ],
            onChanged: _busy ? null : (value) => setState(() => _selected = value),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed:
                (_busy || _selected == null || _selected == _saved) ? null : _save,
            icon: const Icon(Icons.save_outlined),
            label: Text(_busy
                ? 'Saving…'
                : _saved == null
                    ? 'Save to history'
                    : 'Update grown crop'),
          ),
          if (_selected == null)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text(
                'Choose the crop you grew to enable saving.',
                style: TextStyle(fontSize: 11, color: kSoft),
              ),
            ),
        ],
      ),
    );
  }
}
