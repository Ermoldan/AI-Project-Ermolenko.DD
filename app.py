from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import project


def ensure_model_exists() -> bool:
    model_path = project.MODELS_DIR / "rf_3w.joblib"
    cols_path = project.MODELS_DIR / "feature_columns.json"
    return model_path.exists() and cols_path.exists()


def save_uploaded_csv(uploaded) -> Path:
    incoming_dir = project.BASE_DIR / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = incoming_dir / f"uploaded_{stamp}.csv"
    out_path.write_bytes(uploaded.getvalue())
    return out_path


def main() -> None:
    st.set_page_config(page_title="3W Oil&Gas Demo", page_icon=":bar_chart:", layout="wide")
    st.title("3W Mini App: Predskazanie Sostoyaniya Skvazhiny")
    st.write(
        "Zagruzi CSV s dannymi datchikov, i prilozhenie vernet klass sostoyaniya "
        "skvazhiny s ponyatnym opisaniem."
    )

    with st.expander("Spravka po klassam", expanded=True):
        st.dataframe(project.class_reference_table(), use_container_width=True, hide_index=True)

    if not ensure_model_exists():
        st.error(
            "Model files not found. Run training first:\n"
            "`python project.py`"
        )
        st.stop()

    uploaded = st.file_uploader("Zagruzi CSV fail", type=["csv"])
    if not uploaded:
        st.info("Ozhidayu CSV fail dlya analiza.")
        return

    try:
        preview_df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Ne udalos prochitat CSV: {exc}")
        return

    st.subheader("Predprosmotr dannyh")
    st.dataframe(preview_df.head(20), use_container_width=True)
    st.caption(f"Rows: {len(preview_df)} | Columns: {len(preview_df.columns)}")

    if st.button("Zapustit predskazanie", type="primary"):
        try:
            csv_path = save_uploaded_csv(uploaded)
            result = project.predict_file(csv_path)
            report_path = project.write_prediction_report(
                file_path=csv_path,
                pred_label=int(result["pred_label"]),
                top_prob=result["top_prob"],
                ranked=result["ranked"],
            )

            st.success("Predskazanie uspeshno vypolneno.")
            st.subheader("Osnovnoi rezultat")
            st.write(f"Class ID: `{result['pred_label']}`")
            st.write(f"Class name: `{result['pred_name']}`")
            st.write(f"Poyasnenie: {result['pred_desc']}")
            if result["top_prob"] is not None:
                st.write(f"Veroyatnost: `{float(result['top_prob']):.4f}`")
            st.write(f"Uroven uverennosti: `{result['confidence']}`")

            ranked = result["ranked"]
            if ranked:
                top_df = pd.DataFrame(
                    [
                        {
                            "class_id": int(cls),
                            "class_name": project.class_name(int(cls)),
                            "description": project.class_description(int(cls)),
                            "probability": float(prob),
                        }
                        for cls, prob in ranked[:3]
                    ]
                )
                st.subheader("Top-3 gipotezy")
                st.dataframe(top_df, use_container_width=True, hide_index=True)
                st.bar_chart(top_df.set_index("class_name")["probability"])

            report_text = report_path.read_text(encoding="utf-8")
            st.subheader("Txt otchet")
            st.code(report_text, language="text")
            st.download_button(
                label="Skachat otchet (.txt)",
                data=report_text,
                file_name=report_path.name,
                mime="text/plain",
            )
            st.caption(f"Otchet sohranen lokalno: {report_path}")
        except Exception as exc:
            st.error(f"Oshibka vo vremya predskazaniya: {exc}")


if __name__ == "__main__":
    main()
