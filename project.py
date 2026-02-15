from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


BASE_DIR = Path(__file__).resolve().parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw" / "3w"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

SENSOR_COLUMNS = [
    "P-PDG",
    "P-TPT",
    "T-TPT",
    "P-MON-CKP",
    "T-JUS-CKP",
    "P-JUS-CKGL",
    "T-JUS-CKGL",
    "QGL",
]

ABS_VALUE_LIMIT = 1e20

# Class names from 3W dataset 1.0 (paper table), rendered in Latin translit.
CLASS_NAME_MAP: dict[int, str] = {
    0: "normalnaya_rabota",
    1: "rezkii_rost_bsw",
    2: "lozhnoe_zakrytie_dhsv",
    3: "tyazhelyi_slugging",
    4: "nestabilnost_potoka",
    5: "bystraya_poterya_proizvoditelnosti",
    6: "bystroe_suzhenie_v_pck",
    7: "otlozheniya_v_pck",
    8: "gidrat_v_linii_dobychi",
}

CLASS_DESCRIPTION_MAP: dict[int, str] = {
    0: "Normalnyi rabochii rezhim skvazhiny bez anomalii.",
    1: "Rezkii rost obvodnennosti (BSW), kachestvo dobychi uhudshaetsya.",
    2: "Lozhnoe zakrytie DHSV (podzemnyi klapan zakrylsya oshibochno).",
    3: "Tyazhelyi slugging, neravnomernyi potok s krupnymi probkami.",
    4: "Nestabilnost potoka, kolebaniya davleniya i rashoda.",
    5: "Bystraya poterya proizvoditelnosti skvazhiny.",
    6: "Bystroe suzhenie v PCK (zasor/ogranichenie v choke-zone).",
    7: "Otlozheniya v PCK, postupennoe uhudshenie prohodimosti.",
    8: "Gidrat v linii dobychi, risk blokirovki potoka.",
}


@dataclass
class DatasetPack:
    x: pd.DataFrame
    y: pd.Series
    source_files: list[Path]


def class_name(label: int) -> str:
    return CLASS_NAME_MAP.get(int(label), "neizvestnyi_klass")


def class_description(label: int) -> str:
    return CLASS_DESCRIPTION_MAP.get(int(label), "Opisanie dlya etogo klassa ne zadano.")


def class_reference_table() -> pd.DataFrame:
    rows = []
    for cls in sorted(CLASS_NAME_MAP.keys()):
        rows.append(
            {
                "class_id": int(cls),
                "class_name": class_name(int(cls)),
                "description": class_description(int(cls)),
            }
        )
    return pd.DataFrame(rows)


def confidence_text(prob: float | None) -> str:
    if prob is None:
        return "unknown_confidence"
    if prob >= 0.90:
        return "high_confidence"
    if prob >= 0.70:
        return "medium_confidence"
    return "low_confidence"


def get_csv_files(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(
            f"Dataset folder not found: {root}. "
            "Check that CSV files are in data/raw/3w/0..8"
        )
    files = sorted(root.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in folder: {root}")
    return files


def safe_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    series = pd.to_numeric(frame[column], errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan)
    # 3W has rare sentinel-like values that are physically impossible.
    series = series.mask(series.abs() > ABS_VALUE_LIMIT, np.nan)
    return series


def compute_trend(values: pd.Series) -> float:
    clean = values.dropna().to_numpy()
    if clean.size < 2:
        return 0.0
    x_axis = np.arange(clean.size, dtype=float)
    slope, _ = np.polyfit(x_axis, clean, 1)
    return float(slope)


def extract_features(ts_frame: pd.DataFrame, file_label: int, file_path: Path) -> dict[str, float]:
    features: dict[str, float] = {
        "label": float(file_label),
        "n_rows": float(len(ts_frame)),
    }

    for sensor in SENSOR_COLUMNS:
        series = safe_numeric_series(ts_frame, sensor)
        features[f"{sensor}_mean"] = float(series.mean(skipna=True))
        features[f"{sensor}_std"] = float(series.std(skipna=True))
        features[f"{sensor}_min"] = float(series.min(skipna=True))
        features[f"{sensor}_max"] = float(series.max(skipna=True))
        features[f"{sensor}_median"] = float(series.median(skipna=True))
        features[f"{sensor}_p10"] = float(series.quantile(0.10))
        features[f"{sensor}_p90"] = float(series.quantile(0.90))
        features[f"{sensor}_trend"] = compute_trend(series)
        features[f"{sensor}_nan_ratio"] = float(series.isna().mean())

    # Extra time-based features from timestamp column.
    if "timestamp" in ts_frame.columns:
        parsed_dt = pd.to_datetime(ts_frame["timestamp"], errors="coerce")
        features["duration_sec"] = float((parsed_dt.max() - parsed_dt.min()).total_seconds())
        features["valid_timestamp_ratio"] = float(parsed_dt.notna().mean())
    else:
        features["duration_sec"] = 0.0
        features["valid_timestamp_ratio"] = 0.0

    return features


def infer_file_label(file_path: Path, frame: pd.DataFrame) -> int:
    # Primary source of class label: parent folder name (0..8).
    folder_name = file_path.parent.name
    if folder_name.isdigit():
        return int(folder_name)

    # Fallback: if folder name is not numeric, use class column.
    if "class" in frame.columns:
        class_values = pd.to_numeric(frame["class"], errors="coerce").dropna()
        if not class_values.empty:
            return int(class_values.mode().iloc[0])

    raise ValueError(f"Cannot infer class label for file: {file_path}")


def build_dataset(csv_files: Iterable[Path]) -> DatasetPack:
    rows: list[dict[str, float]] = []
    source_files: list[Path] = []

    for file_path in csv_files:
        frame = pd.read_csv(file_path)
        label = infer_file_label(file_path, frame)
        row = extract_features(frame, label, file_path)
        rows.append(row)
        source_files.append(file_path)

    dataset = pd.DataFrame(rows)
    y = dataset["label"].astype(int)
    x = dataset.drop(columns=["label"])
    x = sanitize_feature_table(x)
    return DatasetPack(x=x, y=y, source_files=source_files)


def sanitize_feature_table(x: pd.DataFrame) -> pd.DataFrame:
    clean = x.copy()
    clean = clean.replace([np.inf, -np.inf], np.nan)
    clean = clean.mask(clean.abs() > ABS_VALUE_LIMIT, np.nan)
    return clean


def drop_fully_empty_columns(x: pd.DataFrame) -> pd.DataFrame:
    return x.dropna(axis=1, how="all")


def train_and_evaluate(pack: DatasetPack) -> tuple[Pipeline, dict[str, object]]:
    x_train, x_test, y_train, y_test = train_test_split(
        pack.x,
        pack.y,
        test_size=0.2,
        random_state=42,
        stratify=pack.y,
    )

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=42,
                    n_jobs=-1,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    weighted_f1 = f1_score(y_test, y_pred, average="weighted")
    report = classification_report(y_test, y_pred, digits=3)
    cm = confusion_matrix(y_test, y_pred)

    metrics = {
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "report": report,
        "confusion_matrix": cm,
        "x_test": x_test,
        "y_test": y_test,
        "y_pred": y_pred,
    }
    return model, metrics


def save_outputs(model: Pipeline, metrics: dict[str, object]) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / "rf_3w.joblib"
    joblib.dump(model, model_path)
    feature_columns_path = MODELS_DIR / "feature_columns.json"
    with feature_columns_path.open("w", encoding="utf-8") as f:
        json.dump(metrics["feature_columns"], f, ensure_ascii=True, indent=2)

    cm = metrics["confusion_matrix"]
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("3W Confusion Matrix")
    plt.xlabel("Predicted label")
    plt.ylabel("True label")
    plt.tight_layout()
    cm_path = REPORTS_DIR / "confusion_matrix.png"
    plt.savefig(cm_path, dpi=150)
    plt.close()

    report_path = REPORTS_DIR / "classification_report.txt"
    with report_path.open("w", encoding="utf-8") as f:
        f.write("3W RandomForest classification report\n\n")
        f.write(f"Macro F1: {metrics['macro_f1']:.4f}\n")
        f.write(f"Weighted F1: {metrics['weighted_f1']:.4f}\n\n")
        f.write(str(metrics["report"]))

    print(f"Model saved: {model_path}")
    print(f"Feature columns saved: {feature_columns_path}")
    print(f"Confusion matrix saved: {cm_path}")
    print(f"Report saved: {report_path}")


def run_training() -> None:
    print("Step 1/5: Searching CSV files...")
    csv_files = get_csv_files(RAW_DATA_DIR)
    print(f"Files found: {len(csv_files)}")

    print("Step 2/5: Building feature table...")
    pack = build_dataset(csv_files)
    pack = DatasetPack(
        x=drop_fully_empty_columns(pack.x),
        y=pack.y,
        source_files=pack.source_files,
    )
    print(f"Feature table shape: {pack.x.shape}")
    print(f"Classes: {sorted(pack.y.unique().tolist())}")
    print("Class mapping:")
    for c in sorted(pack.y.unique().tolist()):
        print(f"  {c}: {class_name(int(c))}")

    print("Step 3/5: Training model...")
    model, metrics = train_and_evaluate(pack)
    metrics["feature_columns"] = list(pack.x.columns)

    print("Step 4/5: Test metrics")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"Weighted F1: {metrics['weighted_f1']:.4f}")
    print("\nClassification report:")
    print(metrics["report"])

    print("Step 5/5: Saving artifacts...")
    save_outputs(model, metrics)
    print("Done.")


def extract_inference_features(file_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(file_path)
    row = extract_features(frame, file_label=0, file_path=file_path)
    row.pop("label", None)
    x = pd.DataFrame([row])
    x = sanitize_feature_table(x)
    return x


def load_feature_columns() -> list[str]:
    path = MODELS_DIR / "feature_columns.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Feature column file not found: {path}. Run training first (python project.py)."
        )
    with path.open("r", encoding="utf-8") as f:
        cols = json.load(f)
    if not isinstance(cols, list) or not cols:
        raise ValueError(f"Feature column file is invalid: {path}")
    return [str(c) for c in cols]


def predict_file(file_path: Path) -> dict[str, object]:
    model_path = MODELS_DIR / "rf_3w.joblib"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_path}. Run training first (python project.py)."
        )
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    model = joblib.load(model_path)
    feature_columns = load_feature_columns()
    x_new = extract_inference_features(file_path)
    x_new = x_new.reindex(columns=feature_columns, fill_value=np.nan)

    pred = model.predict(x_new)
    pred_label = int(pred[0])
    pred_name = class_name(pred_label)
    pred_desc = class_description(pred_label)

    ranked: list[tuple[int, float]] | None = None
    top_prob: float | None = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(x_new)[0]
        classes = list(model.classes_)
        ranked = sorted(
            [(int(c), float(p)) for c, p in zip(classes, proba)],
            key=lambda item: item[1],
            reverse=True,
        )
        top_prob = ranked[0][1]

    return {
        "file_path": file_path,
        "pred_label": pred_label,
        "pred_name": pred_name,
        "pred_desc": pred_desc,
        "top_prob": top_prob,
        "confidence": confidence_text(top_prob),
        "ranked": ranked,
    }


def run_prediction(file_path: Path) -> None:
    result = predict_file(file_path)
    pred_label = int(result["pred_label"])
    pred_name = str(result["pred_name"])
    pred_desc = str(result["pred_desc"])
    top_prob = result["top_prob"]
    ranked = result["ranked"]
    report_path: Path

    if ranked:
        top_class, top_prob = ranked[0]
        report_path = write_prediction_report(
            file_path=file_path,
            pred_label=pred_label,
            top_prob=float(top_prob),
            ranked=ranked,
        )

        print(f"Input file: {file_path}")
        print(f"Predicted class: {pred_label} ({pred_name})")
        print(f"Human meaning: {pred_desc}")
        print(
            "Top class by probability: "
            f"{int(top_class)} ({class_name(int(top_class))}) ({top_prob:.4f})"
        )
        print("Top-3 class probabilities:")
        for cls, p in ranked[:3]:
            print(f"  class {int(cls)} ({class_name(int(cls))}): {p:.4f}")
    else:
        report_path = write_prediction_report(
            file_path=file_path,
            pred_label=pred_label,
            top_prob=None,
            ranked=None,
        )
        print(f"Input file: {file_path}")
        print(f"Predicted class: {pred_label} ({pred_name})")
        print(f"Human meaning: {pred_desc}")
    print(f"Human-readable summary saved: {report_path}")


def write_prediction_report(
    file_path: Path,
    pred_label: int,
    top_prob: float | None,
    ranked: list[tuple[int, float]] | None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"prediction_summary_{stamp}.txt"

    lines: list[str] = []
    lines.append("AI summary for oil-and-gas skvazhina")
    lines.append("")
    lines.append(f"Data file: {file_path}")
    lines.append(f"Prediction time: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("Main result:")
    lines.append(f"- Predicted class: {pred_label}")
    lines.append(f"- Class name: {class_name(pred_label)}")
    lines.append(f"- Human meaning: {class_description(pred_label)}")
    if top_prob is not None:
        lines.append(f"- Probability: {top_prob:.4f}")
    lines.append(f"- Confidence level: {confidence_text(top_prob)}")
    lines.append("")
    lines.append("Plain-language conclusion:")
    if top_prob is None:
        lines.append(
            "Model opredelila naibolee veroyatnyi klass sostoyaniya skvazhiny, "
            "no bez chislennoi ocenki uverennosti."
        )
    else:
        lines.append(
            f"Model schitaet, chto na skvazhine nablyudaetsya "
            f"'{class_name(pred_label)}' ({class_description(pred_label)}). "
            f"Uverennost modeli: {top_prob:.2%}."
        )
    lines.append("")

    if ranked:
        lines.append("Top-3 hypotheses:")
        for idx, (cls, prob) in enumerate(ranked[:3], start=1):
            lines.append(
                f"{idx}. class {int(cls)} | {class_name(int(cls))} | "
                f"{class_description(int(cls))} | p={prob:.4f}"
            )
        lines.append("")

    lines.append("Recommendation:")
    lines.append(
        "Ispolzui etot rezultat kak signal dlya analiza inzhenerom: "
        "proverit sensory, trendy i tekhnologicheskii rezhim skvazhiny."
    )

    with report_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="3W project: train model or predict class for one CSV file."
    )
    parser.add_argument(
        "--predict",
        type=str,
        default=None,
        help="Path to one CSV file for inference.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.predict:
        run_prediction(Path(args.predict))
    else:
        run_training()


if __name__ == "__main__":
    main()
