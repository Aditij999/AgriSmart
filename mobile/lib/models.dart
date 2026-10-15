/// Data models mirroring the FastAPI response schemas.
library;

class User {
  User({required this.id, required this.username, this.email, this.fullName});

  final int id;
  final String username;
  final String? email;
  final String? fullName;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as int,
        username: json['username'] as String,
        email: json['email'] as String?,
        fullName: json['full_name'] as String?,
      );
}

class CropScore {
  CropScore({required this.crop, required this.probability});

  final String crop;
  final double probability;

  /// Percentage form for display.
  double get percent => probability * 100;

  factory CropScore.fromJson(Map<String, dynamic> json) => CropScore(
        crop: json['crop'] as String,
        probability: (json['probability'] as num).toDouble(),
      );
}

class NutrientStatus {
  NutrientStatus({
    required this.nutrient,
    required this.current,
    required this.ideal,
    required this.gap,
    required this.action,
    required this.status,
  });

  final String nutrient;
  final double current;
  final double ideal;
  final double gap;
  final String action;
  final String status;

  factory NutrientStatus.fromJson(String nutrient, Map<String, dynamic> json) =>
      NutrientStatus(
        nutrient: nutrient,
        current: (json['current'] as num).toDouble(),
        ideal: (json['ideal'] as num).toDouble(),
        gap: (json['gap'] as num).toDouble(),
        action: json['action'] as String? ?? '',
        status: json['status'] as String? ?? '',
      );
}

class FertilizerRec {
  FertilizerRec({
    required this.fertilizer,
    required this.npkRatio,
    required this.nutrient,
    required this.condition,
    required this.doseNote,
    required this.reason,
  });

  final String fertilizer;
  final String npkRatio;
  final String nutrient;
  final String condition;
  final String doseNote;
  final String reason;

  factory FertilizerRec.fromJson(Map<String, dynamic> json) => FertilizerRec(
        fertilizer: json['fertilizer'] as String? ?? '',
        npkRatio: json['npk_ratio'] as String? ?? '',
        nutrient: json['nutrient'] as String? ?? '',
        condition: json['condition'] as String? ?? '',
        doseNote: json['dose_note'] as String? ?? '',
        reason: json['reason'] as String? ?? '',
      );
}

class SoilInput {
  SoilInput({
    required this.nitrogen,
    required this.phosphorus,
    required this.potassium,
    required this.ph,
    required this.temperature,
    required this.rainfall,
  });

  final double nitrogen;
  final double phosphorus;
  final double potassium;
  final double ph;
  final double temperature;
  final double rainfall;

  Map<String, dynamic> toJson() => {
        'nitrogen': nitrogen,
        'phosphorus': phosphorus,
        'potassium': potassium,
        'ph': ph,
        'temperature': temperature,
        'rainfall': rainfall,
      };

  factory SoilInput.fromJson(Map<String, dynamic> json) => SoilInput(
        nitrogen: (json['nitrogen'] as num).toDouble(),
        phosphorus: (json['phosphorus'] as num).toDouble(),
        potassium: (json['potassium'] as num).toDouble(),
        ph: (json['ph'] as num).toDouble(),
        temperature: (json['temperature'] as num).toDouble(),
        rainfall: (json['rainfall'] as num).toDouble(),
      );
}

class PredictionResult {
  PredictionResult({
    required this.id,
    required this.createdAt,
    required this.label,
    required this.soilInput,
    required this.chosenCrop,
    required this.recommendedCrop,
    required this.recommendedCropProbability,
    required this.predictedYieldKgHa,
    required this.topCrops,
    required this.soilAnalysis,
    required this.fertilizerRecs,
    required this.fertilizerSummary,
    required this.cropPrimaryFertilizer,
    required this.yieldInterpretation,
    this.grownCrop,
  });

  final int? id;
  final DateTime? createdAt;
  final String? label;
  final SoilInput soilInput;
  final String chosenCrop;
  final String? recommendedCrop;
  final double? recommendedCropProbability;
  final double? predictedYieldKgHa;
  final List<CropScore> topCrops;
  final List<NutrientStatus> soilAnalysis;
  final List<FertilizerRec> fertilizerRecs;
  final String fertilizerSummary;
  final String? cropPrimaryFertilizer;
  final String yieldInterpretation;

  /// The crop the farmer finally grew (drives crop-rotation alerts); null until recorded.
  final String? grownCrop;

  bool get cropMismatch =>
      recommendedCrop != null && recommendedCrop != chosenCrop;

  factory PredictionResult.fromJson(Map<String, dynamic> json) {
    final soilAnalysisJson =
        (json['soil_analysis'] as Map?)?.cast<String, dynamic>() ?? {};
    final fertilizer =
        (json['fertilizer'] as Map?)?.cast<String, dynamic>() ?? {};
    final yieldJson =
        (json['yield_prediction'] as Map?)?.cast<String, dynamic>() ?? {};
    final primary = (fertilizer['crop_primary'] as Map?)?.cast<String, dynamic>();

    return PredictionResult(
      id: json['id'] as int?,
      createdAt: json['created_at'] == null
          ? null
          : DateTime.parse(json['created_at'] as String).toLocal(),
      label: json['label'] as String?,
      soilInput: SoilInput.fromJson(
          (json['soil_input'] as Map).cast<String, dynamic>()),
      chosenCrop: json['chosen_crop'] as String? ?? '',
      recommendedCrop: json['recommended_crop'] as String?,
      recommendedCropProbability:
          (json['recommended_crop_probability'] as num?)?.toDouble(),
      predictedYieldKgHa: (json['predicted_yield_kg_ha'] as num?)?.toDouble(),
      topCrops: ((json['top_crops'] as List?) ?? [])
          .map((item) => CropScore.fromJson((item as Map).cast<String, dynamic>()))
          .toList(),
      soilAnalysis: soilAnalysisJson.entries
          .map((entry) => NutrientStatus.fromJson(
              entry.key, (entry.value as Map).cast<String, dynamic>()))
          .toList(),
      fertilizerRecs: ((fertilizer['generic_recs'] as List?) ?? [])
          .map((item) =>
              FertilizerRec.fromJson((item as Map).cast<String, dynamic>()))
          .toList(),
      fertilizerSummary: fertilizer['combined_summary'] as String? ?? '',
      cropPrimaryFertilizer: primary == null
          ? null
          : '${primary['fertilizer']} — ${primary['note']}',
      yieldInterpretation: yieldJson['interpretation'] as String? ?? '',
      grownCrop: json['grown_crop'] as String?,
    );
  }
}

class HistoryItem {
  HistoryItem({
    required this.id,
    required this.createdAt,
    required this.label,
    required this.chosenCrop,
    required this.recommendedCrop,
    required this.predictedYieldKgHa,
    required this.soilInput,
    this.grownCrop,
  });

  final int id;
  final DateTime createdAt;
  final String? label;
  final String chosenCrop;
  final String? recommendedCrop;
  final double? predictedYieldKgHa;
  final SoilInput soilInput;

  /// Crop actually grown for this run; null until the farmer records it.
  final String? grownCrop;

  factory HistoryItem.fromJson(Map<String, dynamic> json) => HistoryItem(
        id: json['id'] as int,
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        label: json['label'] as String?,
        chosenCrop: json['chosen_crop'] as String? ?? '',
        recommendedCrop: json['recommended_crop'] as String?,
        predictedYieldKgHa: (json['predicted_yield_kg_ha'] as num?)?.toDouble(),
        soilInput: SoilInput.fromJson(json),
        grownCrop: json['grown_crop'] as String?,
      );
}

/// One crop-rotation warning for one field, computed by the backend with the
/// same rules the website uses (`GET /api/history/rotation`).
class RotationAdvice {
  RotationAdvice({
    required this.level,
    required this.crop,
    required this.streak,
    required this.headline,
    required this.reason,
    required this.suggest,
    required this.field,
  });

  /// "alert" (same crop 3+ times in a row) or "watch".
  final String level;
  final String crop;
  final int streak;
  final String headline;
  final String reason;
  final List<String> suggest;

  /// The run label the advice applies to ('' = unlabeled runs).
  final String field;

  bool get isAlert => level == 'alert';

  factory RotationAdvice.fromJson(Map<String, dynamic> json) => RotationAdvice(
        level: json['level'] as String? ?? 'watch',
        crop: json['crop'] as String? ?? '',
        streak: (json['streak'] as num?)?.toInt() ?? 0,
        headline: json['headline'] as String? ?? '',
        reason: json['reason'] as String? ?? '',
        suggest: ((json['suggest'] as List?) ?? [])
            .map((item) => item.toString())
            .toList(),
        field: json['field'] as String? ?? '',
      );
}

class CompareRow {
  CompareRow({
    required this.field,
    required this.unit,
    required this.values,
    required this.changed,
  });

  final String field;
  final String unit;
  final List<String> values;
  final bool changed;

  factory CompareRow.fromJson(Map<String, dynamic> json) => CompareRow(
        field: json['field'] as String,
        unit: json['unit'] as String? ?? '',
        values: ((json['values'] as List?) ?? [])
            .map((value) => value == null ? '—' : value.toString())
            .toList(),
        changed: json['changed'] as bool? ?? false,
      );
}

/// One plain-language line in the change summary.
///
/// [direction]: up | down | changed | same.
/// [tone]: positive | negative | neutral — only positive/negative where the
/// analysis itself defines better/worse (yield, status moving to/from Optimal).
/// [kind] is only set for key changes: soil | crop | yield | fertilizer | adjustment.
class ChangeItem {
  ChangeItem({
    required this.text,
    required this.direction,
    required this.tone,
    this.kind = '',
  });

  final String text;
  final String direction;
  final String tone;
  final String kind;

  factory ChangeItem.fromJson(Map<String, dynamic> json) => ChangeItem(
        text: json['text'] as String? ?? '',
        direction: json['direction'] as String? ?? 'changed',
        tone: json['tone'] as String? ?? 'neutral',
        kind: json['kind'] as String? ?? '',
      );
}

class ChangeSection {
  ChangeSection({required this.id, required this.title, required this.items});

  final String id;
  final String title;
  final List<ChangeItem> items;

  factory ChangeSection.fromJson(Map<String, dynamic> json) => ChangeSection(
        id: json['id'] as String? ?? '',
        title: json['title'] as String? ?? '',
        items: _parseList(json['items'], ChangeItem.fromJson),
      );
}

class EntryRef {
  EntryRef({required this.id, required this.name, required this.createdAt});

  final int? id;
  final String name;
  final DateTime? createdAt;

  factory EntryRef.fromJson(Map<String, dynamic> json) => EntryRef(
        id: json['id'] as int?,
        name: json['name'] as String? ?? '',
        createdAt: json['created_at'] == null
            ? null
            : DateTime.parse(json['created_at'] as String).toLocal(),
      );
}

class YieldChange {
  YieldChange({
    required this.before,
    required this.after,
    required this.delta,
    required this.percent,
    required this.tone,
  });

  final double before;
  final double after;
  final double delta;
  final double? percent;
  final String tone;

  factory YieldChange.fromJson(Map<String, dynamic> json) => YieldChange(
        before: (json['before'] as num).toDouble(),
        after: (json['after'] as num).toDouble(),
        delta: (json['delta'] as num).toDouble(),
        percent: (json['percent'] as num?)?.toDouble(),
        tone: json['tone'] as String? ?? 'neutral',
      );
}

class CropChange {
  CropChange({required this.before, required this.after, required this.changed});

  final String before;
  final String after;
  final bool changed;

  factory CropChange.fromJson(Map<String, dynamic> json) => CropChange(
        before: json['before'] as String? ?? '',
        after: json['after'] as String? ?? '',
        changed: json['changed'] as bool? ?? false,
      );
}

/// What changed between two saved analyses (earlier -> later).
class ChangeStep {
  ChangeStep({
    required this.fromEntry,
    required this.toEntry,
    required this.hasChanges,
    required this.keyChanges,
    required this.interpretation,
    required this.cropChange,
    required this.yieldChange,
    required this.sections,
    required this.notes,
  });

  final EntryRef fromEntry;
  final EntryRef toEntry;
  final bool hasChanges;
  final List<ChangeItem> keyChanges;
  final List<String> interpretation;
  final CropChange? cropChange;
  final YieldChange? yieldChange;
  final List<ChangeSection> sections;
  final List<String> notes;

  factory ChangeStep.fromJson(Map<String, dynamic> json) => ChangeStep(
        fromEntry: EntryRef.fromJson(
            (json['from_entry'] as Map).cast<String, dynamic>()),
        toEntry:
            EntryRef.fromJson((json['to_entry'] as Map).cast<String, dynamic>()),
        hasChanges: json['has_changes'] as bool? ?? false,
        keyChanges: _parseList(json['key_changes'], ChangeItem.fromJson),
        interpretation: ((json['interpretation'] as List?) ?? [])
            .map((line) => line.toString())
            .toList(),
        cropChange: json['crop_change'] == null
            ? null
            : CropChange.fromJson(
                (json['crop_change'] as Map).cast<String, dynamic>()),
        yieldChange: json['yield_change'] == null
            ? null
            : YieldChange.fromJson(
                (json['yield_change'] as Map).cast<String, dynamic>()),
        sections: _parseList(json['sections'], ChangeSection.fromJson),
        notes: ((json['notes'] as List?) ?? [])
            .map((line) => line.toString())
            .toList(),
      );
}

class CompareSummary {
  CompareSummary({required this.steps, required this.overall});

  /// One step per consecutive pair, oldest -> newest.
  final List<ChangeStep> steps;

  /// First -> last; only present when three or more analyses are compared.
  final ChangeStep? overall;

  factory CompareSummary.fromJson(Map<String, dynamic> json) => CompareSummary(
        steps: _parseList(json['steps'], ChangeStep.fromJson),
        overall: json['overall'] == null
            ? null
            : ChangeStep.fromJson(
                (json['overall'] as Map).cast<String, dynamic>()),
      );
}

List<T> _parseList<T>(
  Object? value,
  T Function(Map<String, dynamic>) parse,
) =>
    ((value as List?) ?? [])
        .map((item) => parse((item as Map).cast<String, dynamic>()))
        .toList();

class CompareResult {
  CompareResult({required this.entries, required this.rows, this.summary});

  /// Ordered oldest -> newest by the server.
  final List<PredictionResult> entries;
  final List<CompareRow> rows;

  /// Null when talking to an older backend that doesn't send a summary; the
  /// screen then falls back to the field-by-field table alone.
  final CompareSummary? summary;

  factory CompareResult.fromJson(Map<String, dynamic> json) => CompareResult(
        entries: ((json['entries'] as List?) ?? [])
            .map((item) =>
                PredictionResult.fromJson((item as Map).cast<String, dynamic>()))
            .toList(),
        rows: ((json['rows'] as List?) ?? [])
            .map((item) => CompareRow.fromJson((item as Map).cast<String, dynamic>()))
            .toList(),
        summary: json['summary'] == null
            ? null
            : CompareSummary.fromJson(
                (json['summary'] as Map).cast<String, dynamic>()),
      );
}

class ChatMessage {
  ChatMessage({
    required this.role,
    required this.text,
    this.source,
    this.plainText,
    this.lang,
  });

  /// "user" or "model" — matches the API's chat history format.
  final String role;
  final String text;
  final String? source;

  /// Language the reply is written in ("en" / "hi" / "mr"), used to pick a
  /// matching text-to-speech voice.
  final String? lang;

  /// The API's `answer_plain` (decoration stripped), used for text-to-speech.
  final String? plainText;

  bool get isUser => role == 'user';

  /// Text suitable for reading aloud.
  String get speakableText =>
      (plainText != null && plainText!.trim().isNotEmpty) ? plainText! : text;

  Map<String, dynamic> toJson() => {'role': role, 'text': text};
}
