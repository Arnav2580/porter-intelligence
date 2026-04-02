# Model Weights

Generated files — do not commit to git.
Regenerate with:

  python generate_full.py    <- production (500K trips)
  python train.py            <- development (20K trips)

Files:
  xgb_fraud_model.json       <- XGBoost fraud detector
  feature_names.json         <- feature column list
  threshold.json             <- tuned classification threshold
  demand_models.pkl          <- Prophet models (12 zones)
  demand_models_meta.json    <- zone list + trained_at
