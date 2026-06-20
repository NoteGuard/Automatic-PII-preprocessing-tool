"""NoteGuard — demo UI.

Run from the repo root:  streamlit run app/streamlit_app.py

Try-it (detect & sanitise) · Metrics & leakage · Governance (Five Safes) · Two-Trust sharing.
Built on the noteguard package (pluggable detectors + patient-consistent transforms).
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from noteguard.data import load_notes, roster_terms  # noqa: E402
from noteguard.detect import CompositeDetector, GazetteerDetector, build_detector  # noqa: E402
from noteguard.evaluate import evaluate  # noqa: E402
from noteguard.pipeline import Pipeline  # noqa: E402
from noteguard.transform import PSEUDONYM, REDACTION, PseudonymVault  # noqa: E402

OUT_DIR = REPO / "data" / "out"
RESULTS = REPO / "results.json"

ENTITY_COLORS = {
    "PERSON": "#ffd6e0", "UK_NHS": "#ffe9b3", "DATE_TIME": "#d4f4dd", "UK_POSTCODE": "#cfe8ff",
    "LOCATION": "#cfe8ff", "RECORD_ID": "#ffd9c2", "PHONE_NUMBER": "#d4f4dd", "EMAIL_ADDRESS": "#d4f4dd",
    "UK_NINO": "#ffe9b3", "GMC": "#f0e0a0", "NMC": "#f0e0a0", "NHS_ODS": "#f0e0a0",
}

st.set_page_config(page_title="NoteGuard", page_icon="🛡️", layout="wide")


@st.cache_resource(show_spinner="Loading detection engine (Presidio + rules) + sample notes…")
def load_engine():
    detector = build_detector(use_presidio=True)
    try:
        notes = load_notes(limit=80)
    except Exception:
        notes = []
    return detector, notes


def highlight(text: str, spans) -> str:
    chosen, last_end = [], -1
    for s in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if s.start >= last_end:
            chosen.append(s)
            last_end = s.end
    out, idx = [], 0
    for s in chosen:
        out.append(html.escape(text[idx:s.start]))
        color = ENTITY_COLORS.get(s.entity_type, "#e0e0e0")
        out.append(
            f'<mark style="background:{color};padding:0 2px;border-radius:3px" '
            f'title="{s.entity_type} ({s.score:.2f})">{html.escape(text[s.start:s.end])}</mark>'
        )
        idx = s.end
    out.append(html.escape(text[idx:]))
    return "".join(out).replace("\n", "<br>")


def scroll_box(inner_html: str, height: int = 340):
    st.markdown(
        f'<div style="height:{height}px;overflow:auto;border:1px solid #ddd;border-radius:8px;'
        f'padding:12px;font-family:ui-monospace,monospace;font-size:13px;line-height:1.5">{inner_html}</div>',
        unsafe_allow_html=True,
    )


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


st.title("🛡️ NoteGuard")
st.caption("Automatic PII sanitisation for NHS clinical notes — clean data in, no identifiers out. "
           "Sanitise-at-source so Trusts can collaborate (incl. federated training) without sharing raw PII.")

detector, NOTES = load_engine()
ROSTER = roster_terms(NOTES) if NOTES else []

tab_try, tab_metrics, tab_gov, tab_trust = st.tabs(
    ["🔎 Try it", "📊 Metrics & leakage", "🏛️ Governance (Five Safes)", "🤝 Two-Trust sharing"]
)

# ---------------------------------------------------------------- Try it
with tab_try:
    c1, c2 = st.columns([3, 2])
    with c2:
        method = st.radio("Transform", [PSEUDONYM, REDACTION],
                          format_func=lambda m: "Pseudonymise (realistic, patient-consistent)"
                          if m == PSEUDONYM else "Redact ([TYPE] tags)")
        use_roster = st.checkbox("Add Trust roster (gazetteer) — catches names NER misses", value=True)
        source = st.radio("Input", ["Sample note", "Paste your own"])
    with c1:
        if source == "Sample note" and NOTES:
            idx = st.number_input("Note index", 0, len(NOTES) - 1, 0, step=1)
            rec = NOTES[int(idx)]
            text, person_id = rec.text, rec.person_id
        else:
            text = st.text_area("Clinical note (messy free-text)", height=200,
                                value="Pt John Smith, NHS no 943 476 5919, DOB 02/03/1981, lives SW1A 1AA. "
                                      "Admitted Ward 9. Reviewed by Dr Lee, GMC 1234567.")
            person_id = "demo"

    if text.strip():
        det = CompositeDetector(detector, GazetteerDetector(ROSTER)) if (use_roster and ROSTER) else detector
        result = Pipeline(det, PseudonymVault()).sanitise(text, method, person_id)
        st.markdown("##### 1) Detected PII (inspect)")
        scroll_box(highlight(text, result.spans))
        st.markdown(f"##### 2) Sanitised note — `{method}`")
        scroll_box(html.escape(result.sanitised).replace("\n", "<br>"))
        st.markdown("##### 3) Audit (counts only — no raw values leave)")
        counts = Counter(s.entity_type for s in result.spans)
        st.dataframe({"entity": list(counts), "removed": list(counts.values())},
                     hide_index=True, width="stretch")

# ---------------------------------------------------------------- Metrics
with tab_metrics:
    st.markdown("Ground truth is **joined from the dataset's structured tables**, so leakage is a real, "
                "measurable re-identification risk — not an estimate.")
    data = load_json(RESULTS)
    n = st.slider("Notes to evaluate (live run)", 50, 1000, 200, step=50)
    if st.button("▶ Run evaluation (presidio+rules)"):
        with st.spinner("Evaluating…"):
            recs = load_notes(limit=n)
            res = evaluate(recs, detector, PSEUDONYM).to_dict()
            data = {"presidio+rules": res}
            RESULTS.write_text(json.dumps(data, indent=2), encoding="utf-8")

    if data:
        name = "presidio+rules" if "presidio+rules" in data else next(iter(data))
        r = data[name]
        leak = r["leakage"]["leakage_rate_pct"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Known identifiers removed", f"{100 - leak:.1f}%")
        m2.metric("Residual leakage", f"{leak:.2f}%")
        m3.metric("Notes evaluated", r["notes_evaluated"])
        st.markdown("##### Detection by entity type")
        pe = r["detection"]["per_entity"]
        st.dataframe(
            {"entity": list(pe), "recall": [f"{m['recall']:.0%}" for m in pe.values()],
             "precision": [f"{m['precision']:.0%}" for m in pe.values()],
             "support": [m["support"] for m in pe.values()]},
            hide_index=True, width="stretch",
        )
        st.caption(f"Detector: `{name}`. Precision is a conservative lower bound (counts removal of "
                   "PII not in the tables, e.g. clinician names, as false positives).")
    else:
        st.info("No metrics yet — click **Run evaluation** or run `python run_eval.py --compare`.")

# ---------------------------------------------------------------- Governance
with tab_gov:
    st.markdown("### Mapped to the NHS **Five Safes**")
    safes = {
        "Safe data": "PII removed to DAPB1523/ICO standard across NHS identifiers — NHS number "
                     "(mod-11 + 9-digit context form), names, dates, postcode, clinician GMC/NMC, ODS, "
                     "record UUIDs.",
        "Safe settings": "Detection + sanitisation run **inside** the Trust. Raw CSVs and the vault are "
                         "gitignored and never leave.",
        "Safe outputs": "Only de-identified text + content-free audit logs are emitted; the measured "
                        "residual-leakage rate gates outputs.",
        "Safe people / projects": "Re-identification vault stays Trust-local. Pseudonymised (not "
                                  "anonymised) data is still personal data under UK GDPR — stated honestly.",
        "Adoption path": "Sanitise-at-source layer for an NHS Secure Data Environment / Federated Data "
                         "Platform; next step is FLock.io federated training over the de-identified pools.",
    }
    for k, v in safes.items():
        st.markdown(f"**{k}** — {v}")

# ---------------------------------------------------------------- Two-Trust
with tab_trust:
    st.markdown("Two NHS Trusts collaborate **without sharing sensitive data**: each sanitises locally "
                "and contributes only de-identified notes to a shared pool.")
    summary = load_json(OUT_DIR / "trust_demo_summary.json")
    if st.button("▶ Run two-Trust demo"):
        from noteguard.trust_demo import main as run_trust
        with st.spinner("Sanitising at each Trust…"):
            run_trust()
        summary = load_json(OUT_DIR / "trust_demo_summary.json")

    if summary:
        cols = st.columns(len(summary["trusts"]) + 1)
        for col, t in zip(cols, summary["trusts"]):
            with col:
                st.markdown(f"#### 🏥 {t['trust'].split('(')[0].strip()}")
                st.metric("Notes de-identified", t["notes_deidentified"])
                st.metric("Raw records shared", t["raw_records_shared"])
                st.metric("Residual leaks", t["residual_leaks"])
                st.caption("🔒 raw notes + vault stay local")
        with cols[-1]:
            st.markdown("#### 🟢 Shared SDE pool")
            st.metric("De-identified notes", summary["shared_pool_size"])
            st.metric("Raw records shared", summary["raw_records_shared"])
            st.metric("Total residual leaks", summary["total_residual_leaks"])
            st.caption("→ ready for federated AI / FLock.io")
    else:
        st.info("Click **Run two-Trust demo** or run `python -m noteguard.trust_demo`.")
