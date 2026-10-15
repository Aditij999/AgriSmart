import 'dart:convert';

import 'package:agrismart_mobile/api_client.dart';
import 'package:agrismart_mobile/app_state.dart';
import 'package:agrismart_mobile/main.dart';
import 'package:agrismart_mobile/models.dart';
import 'package:agrismart_mobile/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('shows the login screen when signed out', (tester) async {
    final state = AppState(api: ApiClient(client: MockClient((_) async => http.Response('{}', 200))));
    await state.restoreSession();

    await tester.pumpWidget(
      ChangeNotifierProvider.value(value: state, child: const AgriSmartApp()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Log in'), findsOneWidget);
    expect(find.text('New here? Create an account'), findsOneWidget);
  });

  test('parses a prediction response', () {
    final json = jsonDecode('''
    {
      "id": 7,
      "created_at": "2026-01-01T10:00:00",
      "label": "North field",
      "soil_input": {"nitrogen": 80, "phosphorus": 40, "potassium": 40,
                     "ph": 6.5, "temperature": 25, "rainfall": 800},
      "chosen_crop": "Wheat",
      "recommended_crop": "Jowar",
      "recommended_crop_probability": 0.61,
      "predicted_yield_kg_ha": 2450.5,
      "top_crops": [{"crop": "Jowar", "probability": 0.61}],
      "soil_analysis": {"Nitrogen": {"current": 80, "ideal": 91.8, "gap": 11.8,
                                     "action": "INCREASE", "status": "Low"}},
      "fertilizer": {"generic_recs": [{"fertilizer": "Urea", "npk_ratio": "46-0-0",
                                       "nutrient": "Nitrogen", "condition": "Low",
                                       "dose_note": "2 splits", "reason": "N source"}],
                     "combined_summary": "Apply urea",
                     "crop_primary": {"fertilizer": "19:19:19 NPK", "note": "balanced"}},
      "yield_prediction": {"predicted_yield_kg_ha": 2450.5, "interpretation": "Moderate"}
    }
    ''') as Map<String, dynamic>;

    final result = PredictionResult.fromJson(json);

    expect(result.id, 7);
    expect(result.chosenCrop, 'Wheat');
    expect(result.cropMismatch, isTrue);
    expect(result.topCrops.single.percent, closeTo(61, 0.01));
    expect(result.soilAnalysis.single.status, 'Low');
    expect(result.fertilizerRecs.single.fertilizer, 'Urea');
    expect(result.cropPrimaryFertilizer, contains('19:19:19 NPK'));
  });

  test('capitalises names for display', () {
    expect(displayName('dia'), 'Dia');
    expect(displayName('  ravi kumar '), 'Ravi Kumar');
    expect(displayName('McDonald'), 'McDonald');
    expect(displayName(''), '');
    expect(displayName(null), '');
    expect(userDisplayName(User(id: 1, username: 'dia')), 'Dia');
    expect(userDisplayName(User(id: 1, username: 'dia', fullName: 'dia sharma')),
        'Dia Sharma');
    expect(initialsOf('Dia'), 'DI');
  });

  test('parses a crop-rotation alert and the grown crop on history items', () {
    final advice = RotationAdvice.fromJson({
      'level': 'alert',
      'crop': 'Cotton',
      'streak': 3,
      'headline': 'Cotton has been grown 3 times in a row on this field.',
      'reason': 'Break it with a legume or cereal.',
      'suggest': ['Groundnut', 'Jowar'],
      'field': '',
    });
    expect(advice.isAlert, isTrue);
    expect(advice.suggest, ['Groundnut', 'Jowar']);

    final item = HistoryItem.fromJson({
      'id': 1,
      'created_at': '2026-01-01T10:00:00',
      'label': 'North',
      'chosen_crop': 'Wheat',
      'grown_crop': 'Cotton',
      'nitrogen': 80, 'phosphorus': 40, 'potassium': 40,
      'ph': 6.5, 'temperature': 25, 'rainfall': 800,
    });
    expect(item.grownCrop, 'Cotton');
  });
}
