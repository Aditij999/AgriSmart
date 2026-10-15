# 🌾 CropSense v2 — Maharashtra Black Soil Advisor

## Folder Structure
```
your_folder/
├── app.py
├── crop_model.pkl
├── yield_data.json
├── ideal_params.json
└── static/
    └── index.html
```

## Run
```bash
pip install flask scikit-learn pandas joblib numpy
python app.py
# Open http://localhost:5000
```

## Features
- Step 1: Set rainfall + humidity → auto-detects climate zone + temperature
- Step 2: Adjust N, P, K, pH (farmer-controlled)
- Step 3: Yield chart, best crop, soil improvement advice
