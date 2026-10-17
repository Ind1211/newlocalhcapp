from app.calculators.base import Calculator
from app.calculators.kidney_structured_1 import _num_or_none, _list


class CKDMBDCalculator(Calculator):
    key = "ckd_mbd"

    def compute(self, a: dict) -> dict:
        ca, alb, phos, pth, vitd = (_num_or_none(a.get(k)) for k in ["calcium", "albumin", "phosphate", "pth", "vitaminD"])
        corrected_ca = (ca + 0.8 * (4.0 - alb)) if (ca is not None and alb is not None) else ca
        flags = []
        sev = "good"
        if phos is not None and phos > 4.5:
            flags.append({"text": "Hyperphosphatemia - consider dietary phosphate restriction and/or binder therapy.", "severity": "warning"})
            sev = "warning"
        if corrected_ca is not None:
            if corrected_ca < 8.5:
                flags.append({"text": "Low corrected calcium.", "severity": "caution"})
                if sev == "good":
                    sev = "caution"
            if corrected_ca > 10.5:
                flags.append({"text": "High corrected calcium.", "severity": "warning"})
                sev = "warning"
        if vitd is not None and vitd < 20:
            flags.append({"text": "Vitamin D insufficiency - consider repletion.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if pth is not None and pth > 130:
            flags.append({"text": "PTH elevated - evaluate for secondary hyperparathyroidism; address phosphate, calcium, and vitamin D status first.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": "Values within expected ranges" if not flags else f"{len(flags)} value(s) flagged",
            "headlineSeverity": sev,
            "metrics": [{"label": "Corrected calcium", "value": round(corrected_ca, 1) if corrected_ca is not None else "\u2014", "unit": "mg/dL"}, {"label": "Phosphate", "value": phos if phos is not None else "\u2014", "unit": "mg/dL"}, {"label": "PTH", "value": pth if pth is not None else "\u2014", "unit": "pg/mL"}],
            "flags": flags,
            "notes": "KDIGO does not endorse one universal non-dialysis PTH target - trend values and treat modifiable drivers (phosphate, calcium, vitamin D) rather than anchoring to a single PTH number. Use your lab's local reference ranges.",
        }


class AnemiaCKDCalculator(Calculator):
    key = "anemia_ckd"

    def compute(self, a: dict) -> dict:
        hgb, ferritin, tsat = _num_or_none(a.get("hemoglobin")), _num_or_none(a.get("ferritin")), _num_or_none(a.get("tsat"))
        threshold = 13 if a.get("sex") == "male" else 12
        anemia_present = hgb is not None and hgb < threshold
        flags = []
        sev = "good"
        if anemia_present:
            flags.append({"text": f"Meets WHO/KDIGO anemia threshold (Hb <{threshold} g/dL for {a.get('sex') or 'this'} patient) - evaluate iron studies, B12/folate, and other causes before ESA.", "severity": "caution"})
            sev = "caution"
        if ferritin is not None and tsat is not None and ferritin <= 500 and tsat <= 30:
            flags.append({"text": "Iron indices suggest a trial of iron therapy may be reasonable (KDIGO 2012 anemia guideline threshold).", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if hgb is not None and hgb > 11.5 and a.get("onEsa") == "yes":
            flags.append({"text": "Hemoglobin >11.5 g/dL on ESA - guidelines caution against routinely targeting >11.5-13 g/dL due to cardiovascular risk; reassess dose.", "severity": "warning"})
            sev = "warning"
        return {
            "headline": f"Anemia present (Hb {hgb} g/dL, threshold {threshold})" if anemia_present else "Hemoglobin above the anemia threshold for this patient",
            "headlineSeverity": sev,
            "metrics": [{"label": "Hemoglobin", "value": hgb if hgb is not None else "\u2014", "unit": "g/dL"}, {"label": "Ferritin", "value": ferritin if ferritin is not None else "\u2014", "unit": "ng/mL"}, {"label": "TSAT", "value": tsat if tsat is not None else "\u2014", "unit": "%"}],
            "flags": flags,
            "notes": "Thresholds reflect the KDIGO 2012 anemia-in-CKD guideline. Individualize ESA targets and always investigate reversible causes before dose escalation.",
        }


class CVRiskCalculator(Calculator):
    key = "cv_risk"

    def compute(self, a: dict) -> dict:
        flags = []
        if a.get("hasCkd") == "yes":
            flags.append({"text": "CKD is an established ASCVD risk-enhancing factor per ACC/AHA guidance.", "severity": "caution"})
        if a.get("diabetes") == "yes":
            flags.append({"text": "Diabetes present - additional risk-enhancing factor.", "severity": "caution"})
        if a.get("smoker") == "yes":
            flags.append({"text": "Current smoking - additional risk-enhancing factor and a modifiable one.", "severity": "warning"})
        sbp = _num_or_none(a.get("sbp"))
        if sbp is not None and sbp >= 140:
            flags.append({"text": "Uncontrolled systolic BP (\u2265140) - additional risk-enhancing factor.", "severity": "warning"})
        sev = "warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good")
        return {
            "headline": f"{len(flags)} risk-enhancing factor(s) identified" if flags else "No CKD-specific risk-enhancing factors flagged from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "This tool intentionally does not compute a numeric ASCVD percentage - the ACC/AHA Pooled Cohort Equations require precise, race- and sex-specific coefficients best sourced from a validated calculator rather than reproduced here. Use your institution's validated ASCVD calculator for a numeric estimate, and weigh CKD/albuminuria as an established risk-enhancing factor when interpreting it.",
        }


class HyperkalemiaCalculator(Calculator):
    key = "hyperkalemia"

    def compute(self, a: dict) -> dict:
        k = _num_or_none(a.get("potassium"))
        if k is None:
            return {"headline": "Enter a potassium level.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        sev, tier = "good", "Normal range"
        if k >= 6.5:
            tier, sev = "Severe hyperkalemia", "critical"
        elif k >= 6.0:
            tier, sev = "Moderate-severe hyperkalemia", "warning"
        elif k > 5.5:
            tier, sev = "Mild hyperkalemia", "caution"
        elif k < 3.5:
            tier, sev = "Hypokalemia", "caution"
        flags = []
        ecg = _list(a.get("ecgChanges"))
        if any(e != "none" for e in ecg):
            flags.append({"text": "ECG changes present - treat as an emergency regardless of the exact potassium level; give stabilizing therapy (e.g., IV calcium) without delay.", "severity": "critical"})
            sev = "critical"
        if a.get("hemolyzedSample") == "yes":
            flags.append({"text": "Possible hemolysis - repeat on a fresh, non-hemolyzed sample before acting on this value alone.", "severity": "caution"})
        if sev == "critical" or k >= 6.0:
            flags.append({"text": "Consider urgent treatment (e.g., IV calcium, insulin/glucose, beta-agonist, potassium binders) and evaluate need for urgent dialysis.", "severity": "warning"})
        return {
            "headline": f"{tier} (K {k} mmol/L)", "headlineSeverity": sev,
            "metrics": [{"label": "Potassium", "value": k, "unit": "mmol/L"}], "flags": flags,
            "notes": "Thresholds are general reference ranges - treat the ECG and clinical picture, not the number alone. ECG changes can occur at \"moderate\" levels and be absent at higher ones depending on rate of rise and chronicity.",
        }


class TumorLysisSyndromeCalculator(Calculator):
    key = "tumor_lysis_syndrome"

    def compute(self, a: dict) -> dict:
        ua, k, phos, ca = (_num_or_none(a.get(x)) for x in ["uricAcid", "potassium", "phosphate", "calcium"])
        lab_criteria = 0
        if ua is not None and ua >= 8.0:
            lab_criteria += 1
        if k is not None and k >= 6.0:
            lab_criteria += 1
        if phos is not None and phos >= 4.5:
            lab_criteria += 1
        if ca is not None and ca <= 7.0:
            lab_criteria += 1
        meets_lab_tls = lab_criteria >= 2
        clinical = [c for c in _list(a.get("clinicalFeatures")) if c != "none"]
        meets_clinical_tls = meets_lab_tls and len(clinical) > 0
        if meets_clinical_tls:
            headline, sev = "Meets clinical tumor lysis syndrome criteria", "critical"
        elif meets_lab_tls:
            headline, sev = "Meets laboratory TLS criteria (no clinical TLS yet)", "warning"
        else:
            headline, sev = "Does not meet Cairo-Bishop TLS criteria", "good"
        flags = []
        if meets_clinical_tls:
            flags.append({"text": "Clinical TLS - initiate aggressive IV hydration, consider rasburicase/allopurinol, correct electrolytes, and involve nephrology for possible need for renal replacement therapy.", "severity": "critical"})
        elif meets_lab_tls:
            flags.append({"text": "Laboratory TLS - increase monitoring frequency and continue prophylaxis; watch closely for clinical progression.", "severity": "warning"})
        return {
            "headline": headline, "headlineSeverity": sev,
            "metrics": [{"label": "Lab criteria met", "value": f"{lab_criteria} / 4"}], "flags": flags,
            "notes": "Based on the Cairo-Bishop definition: laboratory TLS requires \u22652 of (uric acid \u22658 mg/dL, K \u22656 mmol/L, phosphate \u22654.5 mg/dL, calcium \u22647 mg/dL - or a \u226525% change from baseline for any of these); clinical TLS additionally requires a renal, cardiac, or neurologic complication. This tool checks absolute thresholds only; the 25%-change-from-baseline pathway isn't calculated here.",
        }


class HyponatremiaWorkupCalculator(Calculator):
    key = "hyponatremia_workup"

    def compute(self, a: dict) -> dict:
        na = _num_or_none(a.get("serumNa"))
        if na is None:
            return {"headline": "Enter serum sodium.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        sev, tier = "good", "Normal range"
        if na < 120:
            tier, sev = "Severe hyponatremia", "critical"
        elif na < 130:
            tier, sev = "Moderate hyponatremia", "warning"
        elif na < 135:
            tier, sev = "Mild hyponatremia", "caution"
        flags = []
        s_osm = _num_or_none(a.get("serumOsm"))
        if s_osm is not None and s_osm >= 275:
            flags.append({"text": "Serum osmolality not low - consider pseudohyponatremia (hyperglycemia, hyperlipidemia, hyperproteinemia) rather than true hypotonic hyponatremia.", "severity": "caution"})
        else:
            u_osm, u_na = _num_or_none(a.get("urineOsm")), _num_or_none(a.get("urineNa"))
            if u_osm is not None and u_osm < 100:
                flags.append({"text": "Low urine osmolality with hypotonic hyponatremia suggests primary polydipsia or low solute intake.", "severity": "caution"})
            else:
                if a.get("volumeStatusExam") == "euvolemic" and u_na is not None and u_na > 30:
                    flags.append({"text": "Euvolemic with concentrated urine and urine Na >30 - consistent with SIADH; evaluate for an underlying cause (malignancy, CNS/pulmonary disease, drugs).", "severity": "warning"})
                if a.get("volumeStatusExam") == "hypovolemic":
                    flags.append({"text": "Hypovolemic hyponatremia - assess for GI/renal/third-space losses; urine Na helps distinguish renal (>20) vs extrarenal (<20) losses.", "severity": "caution"})
                if a.get("volumeStatusExam") == "hypervolemic":
                    flags.append({"text": "Hypervolemic hyponatremia - consider heart failure, cirrhosis, or nephrotic syndrome/advanced CKD.", "severity": "caution"})
        if sev in ("critical", "warning"):
            flags.append({"text": "Correct sodium cautiously - overly rapid correction risks osmotic demyelination syndrome; follow a guideline-based correction-rate limit.", "severity": "warning"})
        return {
            "headline": f"{tier} (Na {na} mmol/L)", "headlineSeverity": sev,
            "metrics": [{"label": "Serum Na", "value": na, "unit": "mmol/L"}], "flags": flags,
            "notes": "A simplified version of the standard serum/urine osmolality + volume-status algorithm for classifying hyponatremia. Real cases often have mixed or evolving pictures - trend values and reassess.",
        }


class NephroticThrombosisRiskCalculator(Calculator):
    key = "nephrotic_thrombosis_risk"

    def compute(self, a: dict) -> dict:
        alb = _num_or_none(a.get("albumin"))
        risk_factors = sum(1 for k in ["priorVte", "immobility", "centralLine", "membranousNephropathy"] if a.get(k) == "yes")
        recommend = False
        if alb is not None and alb < 2.0:
            recommend = True
        elif alb is not None and alb < 2.5 and risk_factors >= 1:
            recommend = True
        flags = [
            {"text": "Albumin low enough (with risk factors, if albumin 2.0-2.5) that many nephrologists consider prophylactic anticoagulation, particularly with membranous nephropathy - weigh bleeding risk and discuss with the patient.", "severity": "warning"}
            if recommend else
            {"text": "Based on entries, prophylactic anticoagulation is less strongly indicated by albumin/risk-factor criteria alone - reassess if albumin falls further or new risk factors develop.", "severity": "caution"}
        ]
        return {
            "headline": "Meets a common threshold for considering prophylactic anticoagulation" if recommend else "Does not clearly meet common anticoagulation thresholds",
            "headlineSeverity": "warning" if recommend else "caution",
            "metrics": [{"label": "Albumin", "value": alb if alb is not None else "\u2014", "unit": "g/dL"}, {"label": "Additional risk factors", "value": risk_factors}], "flags": flags,
            "notes": "Reflects commonly cited thresholds (albumin <2.0-2.5 g/dL, especially with membranous nephropathy or additional VTE risk factors) for discussing prophylactic anticoagulation in nephrotic syndrome - practice varies and this is not a formally validated risk score. Weigh bleeding risk individually.",
        }


class MESTCCalculator(Calculator):
    key = "mest_c"

    def compute(self, a: dict) -> dict:
        if not all(a.get(k) for k in ["mScore", "eScore", "sScore", "tScore", "cScore"]):
            return {"headline": "Select all five components.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        code = f"M{a['mScore']}E{a['eScore']}S{a['sScore']}T{a['tScore']}C{a['cScore']}"
        flags = []
        sev = "good"
        if int(a["tScore"]) >= 1:
            flags.append({"text": "T \u22651 is the component most consistently associated with worse renal survival in Oxford classification validation cohorts.", "severity": "warning"})
            sev = "warning"
        if int(a["cScore"]) >= 1:
            flags.append({"text": "Crescents present - consider immunosuppression per KDIGO IgAN guidance, particularly with \u226525% crescentic glomeruli or rapid GFR decline.", "severity": "warning"})
            sev = "warning"
        if a["eScore"] == "1":
            flags.append({"text": "Endocapillary hypercellularity - evaluate for an active/inflammatory component.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"Oxford score: {code}", "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Oxford (MEST-C) classification is assigned by the reporting pathologist from biopsy; this tool only records the components and reflects published prognostic associations. It does not replace the pathology report.",
        }


class LupusNephritisCalculator(Calculator):
    key = "lupus_nephritis"

    def compute(self, a: dict) -> dict:
        cls = None
        if a.get("mesangialOnly") == "yes":
            cls = "II \u2014 mesangial proliferative" if a.get("mesangialHypercellularity") == "yes" else "I \u2014 minimal mesangial"
        elif a.get("mesangialOnly") == "no":
            pct_scl = _num_or_none(a.get("pctGloballySclerotic"))
            if pct_scl is not None and pct_scl >= 90:
                cls = "VI \u2014 advanced sclerosing (\u226590% globally sclerosed)"
            elif a.get("diffuseOrFocal") == "diffuse":
                cls = f"IV \u2014 diffuse ({'IV-G' if a.get('globalOrSegmental') == 'global' else 'IV-S'})"
            elif a.get("diffuseOrFocal") == "focal":
                cls = "III \u2014 focal"
            if a.get("membranousFeatures") == "yes":
                cls = (cls + " with membranous features (consider co-existing Class V)") if cls else "V \u2014 membranous"
        if not cls:
            return {"headline": "Complete the fields above to estimate a class.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        flags = []
        if "III" in cls or "IV" in cls:
            flags.append({"text": "Proliferative (III/IV) disease typically warrants induction immunosuppression per KDIGO/ACR lupus nephritis guidance.", "severity": "warning"})
        if cls.startswith("V") or "membranous" in cls:
            flags.append({"text": "Membranous features - antiproteinuric therapy, and consider immunosuppression if nephrotic-range proteinuria.", "severity": "caution"})
        if "VI" in cls:
            flags.append({"text": "Advanced sclerosis - focus shifts to supportive care and RRT/transplant planning rather than immunosuppression.", "severity": "warning"})
        return {
            "headline": f"Estimated ISN/RPS Class {cls}", "headlineSeverity": "warning" if any(f["severity"] == "warning" for f in flags) else "caution",
            "metrics": [], "flags": flags,
            "notes": "Simplified decision aid based on the 2003 ISN/RPS criteria (percent glomerular involvement, focal vs. diffuse, global vs. segmental, membranous features, global sclerosis). The pathologist's full report - including activity/chronicity indices - remains authoritative.",
        }


class CardiorenalSyndromeCalculator(Calculator):
    key = "cardiorenal_syndrome"

    def compute(self, a: dict) -> dict:
        if not a.get("primaryTrigger") or not a.get("acuity"):
            return {"headline": "Select both the trigger and acuity.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if a["primaryTrigger"] == "cardiac":
            type_ = "Type 1 \u2014 acute cardiorenal" if a["acuity"] == "acute" else "Type 2 \u2014 chronic cardiorenal"
        elif a["primaryTrigger"] == "renal":
            type_ = "Type 3 \u2014 acute renocardiac" if a["acuity"] == "acute" else "Type 4 \u2014 chronic renocardiac"
        else:
            type_ = "Type 5 \u2014 secondary cardiorenal (systemic condition)"
        flags = []
        if type_.startswith("Type 1"):
            flags.append({"text": "Acute cardiac event driving AKI - manage the precipitating cardiac condition; diuretic-resistant congestion may need ultrafiltration.", "severity": "caution"})
        if type_.startswith("Type 3"):
            flags.append({"text": "AKI driving acute cardiac dysfunction (e.g., via fluid overload or electrolyte shifts) - treat the kidney injury and its metabolic consequences.", "severity": "caution"})
        return {
            "headline": f"Ronco {type_}", "headlineSeverity": "good", "metrics": [], "flags": flags,
            "notes": "Based on the Ronco cardiorenal syndrome classification (triggering organ \u00d7 acuity). Real patients often have overlapping, bidirectional physiology - treat this as a framework for discussion, not a strict diagnostic label.",
        }


class HRSAKICalculator(Calculator):
    key = "hrs_aki"

    def compute(self, a: dict) -> dict:
        keys = ["cirrhosisAscites", "meetsAkiCriteria", "noResponseToVolumeExpansion", "noShock", "noNephrotoxins", "noStructuralDisease"]
        if any(a.get(k) is None for k in keys):
            return {"headline": "Answer all six criteria.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        all_yes = all(a.get(k) == "yes" for k in keys)
        flags = [
            {"text": "Meets ICA criteria for HRS-AKI - consider a vasoconstrictor (e.g., terlipressin) plus albumin per guideline, and evaluate liver transplant candidacy.", "severity": "critical"}
            if all_yes else
            {"text": "Does not meet all ICA HRS-AKI criteria - evaluate other AKI causes (e.g., pre-renal azotemia, ATN, intrinsic kidney disease).", "severity": "caution"}
        ]
        return {
            "headline": "Meets HRS-AKI diagnostic criteria" if all_yes else "Criteria not fully met",
            "headlineSeverity": "critical" if all_yes else "caution",
            "metrics": [], "flags": flags,
            "notes": "Based on the International Club of Ascites (ICA) revised HRS-AKI criteria. This is a diagnosis of exclusion - the full hepatology/nephrology assessment (including renal ultrasound and urinalysis) remains essential.",
        }


class NephroticSyndromeCalculator(Calculator):
    key = "nephrotic_syndrome"

    def compute(self, a: dict) -> dict:
        prot, acr, alb = _num_or_none(a.get("proteinuriaGramsPerDay")), _num_or_none(a.get("spotAcr")), _num_or_none(a.get("albumin"))
        heavy_proteinuria = (prot is not None and prot >= 3.5) or (acr is not None and acr >= 3500)
        low_albumin = alb is not None and alb < 3.0
        criteria_count = sum([heavy_proteinuria, low_albumin, a.get("edema") == "yes", a.get("hyperlipidemia") == "yes"])
        meets_nephrotic = heavy_proteinuria and low_albumin
        causes = [c for c in _list(a.get("secondaryCauses")) if c != "none"]
        flags = []
        if meets_nephrotic:
            flags.append({"text": "Meets core nephrotic syndrome criteria (nephrotic-range proteinuria + hypoalbuminemia) - evaluate for secondary causes and consider nephrology referral/biopsy if no clear secondary cause.", "severity": "warning"})
        if causes:
            flags.append({"text": f"Possible secondary cause(s) flagged ({', '.join(causes)}) - direct workup toward these before assuming a primary glomerular disease.", "severity": "caution"})
        if meets_nephrotic:
            flags.append({"text": "Consider thrombosis risk assessment (nephrotic syndrome raises risk, especially with albumin <2.0-2.5 g/dL) and statin/antiproteinuric therapy.", "severity": "caution"})
        return {
            "headline": "Meets core nephrotic syndrome criteria" if meets_nephrotic else f"{criteria_count}/4 supportive criteria present",
            "headlineSeverity": "warning" if meets_nephrotic else "caution",
            "metrics": [{"label": "Criteria present", "value": f"{criteria_count} / 4"}], "flags": flags,
            "notes": "Nephrotic-range proteinuria is classically \u22653.5 g/day (the spot-ACR correlate used here is an approximation and assay-dependent). This tool flags the syndrome and common secondary causes; it does not replace biopsy-based diagnosis of the underlying glomerular disease.",
        }


class RenalArteryStenosisCalculator(Calculator):
    key = "renal_artery_stenosis"

    def compute(self, a: dict) -> dict:
        pts = 0
        if a.get("resistantHtn") == "yes":
            pts += 2
        if a.get("suddenPulmonaryEdema") == "yes":
            pts += 2
        if a.get("asymmetricKidneySize") == "yes":
            pts += 2
        if a.get("abdominalBruit") == "yes":
            pts += 1
        if a.get("onsetAge") == "<30" or a.get("onsetAge") == ">55":
            pts += 1
        if a.get("smoking") == "yes":
            pts += 1
        if a.get("padCad") == "yes":
            pts += 1
        if a.get("acuteRiseWithAceiArb") == "yes":
            pts += 2
        if pts <= 2:
            category, sev = "Low pretest probability", "good"
        elif pts <= 5:
            category, sev = "Moderate pretest probability", "caution"
        else:
            category, sev = "High pretest probability", "warning"
        flags = []
        if sev != "good":
            flags.append({"text": "Consider renal duplex ultrasound, CT/MR angiography, or referral to vascular/nephrology for further evaluation.", "severity": sev})
        return {
            "headline": f"{category} ({pts} points)", "headlineSeverity": sev,
            "metrics": [{"label": "Clinical clue score", "value": pts}], "flags": flags,
            "notes": "An original, simplified tally of well-known clinical clues for renovascular disease - it is not a validated, published scoring instrument. Use it to structure suspicion, not as a diagnostic score.",
        }


class ANCAVasculitisClassificationCalculator(Calculator):
    key = "anca_vasculitis_classification"

    def compute(self, a: dict) -> dict:
        normal, crescentic, sclerotic = _num_or_none(a.get("pctNormalGlomeruli")), _num_or_none(a.get("pctCrescentic")), _num_or_none(a.get("pctGloballySclerotic"))
        if normal is None or crescentic is None or sclerotic is None:
            return {"headline": "Enter all three percentages.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if normal >= 50:
            cls = "Focal class"
        elif crescentic >= 50:
            cls = "Crescentic class"
        elif sclerotic >= 50:
            cls = "Sclerotic class"
        else:
            cls = "Mixed class"
        flags = []
        sev = "caution"
        if cls == "Focal class":
            flags.append({"text": "Focal class historically carries the best renal prognosis of the four classes.", "severity": "good"})
            sev = "good"
        if cls == "Crescentic class":
            flags.append({"text": "Crescentic class - typically warrants prompt induction immunosuppression (e.g., cyclophosphamide or rituximab plus glucocorticoids); consider plasma exchange if severe/dialysis-dependent per guideline criteria.", "severity": "warning"})
            sev = "warning"
        if cls == "Sclerotic class":
            flags.append({"text": "Sclerotic class historically carries the worst renal prognosis - immunosuppression benefit is limited once this much irreversible scarring is present; focus often shifts toward RRT planning.", "severity": "warning"})
            sev = "warning"
        if cls == "Mixed class":
            flags.append({"text": "Mixed class - intermediate prognosis; treatment generally follows standard ANCA-associated vasculitis induction regimens.", "severity": "caution"})
        return {
            "headline": f"Berden {cls}", "headlineSeverity": sev,
            "metrics": [{"label": "Normal glomeruli", "value": normal, "unit": "%"}, {"label": "Crescentic", "value": crescentic, "unit": "%"}, {"label": "Globally sclerotic", "value": sclerotic, "unit": "%"}], "flags": flags,
            "notes": "Based on the Berden et al. (2010) histopathologic classification of ANCA-associated glomerulonephritis. The pathologist's full report remains authoritative; this simplifies the four-category assignment from the three headline percentages.",
        }


class BosniakClassificationCalculator(Calculator):
    key = "bosniak_classification"

    def compute(self, a: dict) -> dict:
        if a.get("solidComponent") == "yes":
            category, sev = "IV", "critical"
        elif a.get("wallThickness") == "thick-irregular" or a.get("septations") == "thick-irregular":
            category, sev = "III", "warning"
        elif (a.get("septations") == "multiple-thin" or a.get("calcification") == "thick-nodular") and a.get("enhancement") == "yes":
            category, sev = "IIF", "caution"
        elif a.get("septations") == "few-thin" or a.get("calcification") == "thin" or a.get("wallThickness") == "mildly thickened":
            category, sev = "II", "good"
        else:
            category, sev = "I", "good"
        flags = []
        if category == "III":
            flags.append({"text": "Category III lesions are indeterminate - roughly half prove malignant; surgical evaluation or close multidisciplinary discussion is typical.", "severity": "warning"})
        if category == "IV":
            flags.append({"text": "Category IV lesions are managed as renal cell carcinoma until proven otherwise - urologic referral for likely surgical management.", "severity": "critical"})
        if category == "IIF":
            flags.append({"text": "Category IIF requires periodic follow-up imaging (often at 6-12 month intervals) to confirm stability.", "severity": "caution"})
        return {
            "headline": f"Bosniak category {category}", "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "A simplified version of the Bosniak renal cyst classification (I, II, IIF, III, IV) based on wall/septa thickness, calcification, and enhancement. The 2019 revision refines several of these criteria further - the formal radiology report and multidisciplinary review remain authoritative, especially for the III/IV distinction.",
        }


class AASTKidneyInjuryGradeCalculator(Calculator):
    key = "aast_kidney_injury_grade"

    def compute(self, a: dict) -> dict:
        depth = _num_or_none(a.get("lacerationDepthCm"))
        if a.get("pedicleAvulsion") == "yes" or a.get("shatteredKidney") == "yes" or a.get("vascularInjury") == "main-renal-artery-or-vein":
            grade, sev = "V", "critical"
        elif a.get("vascularInjury") == "segmental-vessel" or a.get("collectingSystemInjury") == "yes":
            grade, sev = "IV", "critical"
        elif depth is not None and depth > 1:
            grade, sev = "III", "warning"
        elif depth is not None and 0 < depth <= 1:
            grade, sev = "II", "caution"
        elif a.get("hematoma") and a.get("hematoma") != "none":
            grade, sev = "I", "good"
        else:
            grade, sev = None, None
        if not grade:
            return {"headline": "Enter injury findings to grade.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        flags = []
        if grade in ("IV", "V"):
            flags.append({"text": "High-grade injury - involve urology/trauma surgery promptly; vascular injuries and collecting-system disruption often need intervention (angioembolization, stenting, or surgical exploration).", "severity": "critical"})
        elif grade == "III":
            flags.append({"text": "Grade III is often managed non-operatively in a hemodynamically stable patient, with close monitoring and repeat imaging.", "severity": "caution"})
        return {
            "headline": f"AAST Grade {grade}", "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Based on the AAST (American Association for the Surgery of Trauma) Kidney Injury Scale. Exact depth cutoffs differ slightly between the original 1989 scale and the 2018 revision - confirm which version your trauma service uses. Management increasingly follows hemodynamic stability and clinical trajectory rather than grade alone.",
        }


class PapillaryNecrosisRiskCalculator(Calculator):
    key = "papillary_necrosis_risk"

    def compute(self, a: dict) -> dict:
        rf = [r for r in _list(a.get("riskFactors")) if r != "none"]
        flags = []
        sev = "good"
        if len(rf) >= 2:
            flags.append({"text": "Multiple classic risk factors present - consider renal papillary necrosis in the differential, especially with hematuria and flank pain.", "severity": "warning"})
            sev = "warning"
        elif len(rf) == 1:
            sev = "caution"
        if a.get("sloughedTissuePassed") == "yes":
            flags.append({"text": "Passage of sloughed papillary tissue is a classic (though not universal) finding - strongly consider imaging (CT urogram) to confirm.", "severity": "warning"})
            sev = "warning"
        if a.get("hematuria") == "yes" and a.get("flankPain") == "yes" and len(rf) >= 1:
            flags.append({"text": "Hematuria + flank pain + risk factor(s) - obtain imaging (CT urogram) to evaluate for papillary necrosis and rule out obstruction from sloughed tissue.", "severity": "warning"})
            sev = "warning"
        return {
            "headline": f"{len(rf)} classic risk factor(s) present" if rf else "No classic risk factors selected",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Classic causes are often recalled with the mnemonic \"POSTCARDS\" (Pyelonephritis, Obstruction, Sickle cell, TB, Cirrhosis, Analgesics, Renal vein thrombosis, Diabetes, Systemic vasculitis). This checklist structures suspicion; diagnosis is confirmed by imaging (classic \"ball-on-a-tee\" or ring sign).",
        }


class SickleCellNephropathyCalculator(Calculator):
    key = "sickle_cell_nephropathy"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        acr_ago = _num_or_none(a.get("lastAcrScreenMonthsAgo"))
        if acr_ago is None or acr_ago > 12:
            flags.append({"text": "Annual urine ACR screening is recommended starting in childhood for sickle cell disease and appears overdue or unrecorded.", "severity": "warning"})
            sev = "warning"
        if a.get("hyperfiltrationConcern") == "yes":
            flags.append({"text": "Hyperfiltration is an early, often under-recognized marker of sickle cell nephropathy - trend eGFR/ACR closely even if currently \"normal\" or high.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if a.get("hematuria") == "yes":
            flags.append({"text": "Hematuria in sickle cell disease is often from papillary necrosis or medullary changes - consider imaging if recurrent or gross.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if a.get("hypertension") == "yes":
            flags.append({"text": "Blood pressure targets and ACEi/ARB use for albuminuria follow standard CKD principles once nephropathy is present.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"{len(flags)} item(s) flagged" if flags else "No concerns flagged from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Sickle cell nephropathy often begins with hyperfiltration in childhood, progressing to albuminuria and later CKD - annual ACR screening is recommended starting early. This module structures monitoring; it does not replace hematology/nephrology co-management.",
        }


class AmyloidosisSuspicionCalculator(Calculator):
    key = "amyloidosis_suspicion"

    def compute(self, a: dict) -> dict:
        keys = ["nephroticRangeProteinuria", "cardiacInvolvement", "peripheralNeuropathy", "hepatomegaly", "monoclonalGammopathy", "chronicInflammatoryDisease", "orthostaticHypotension"]
        clues = [k for k in keys if a.get(k) == "yes"]
        sev = "warning" if len(clues) >= 3 else ("caution" if len(clues) >= 1 else "good")
        flags = []
        if len(clues) >= 3:
            flags.append({"text": "Multiple multi-organ clues present - reasonable suspicion for amyloidosis; consider serum/urine free light chains, SPEP/UPEP with immunofixation, and biopsy (fat pad, or the clinically affected organ) with Congo red staining.", "severity": "warning"})
        elif len(clues) >= 1:
            flags.append({"text": "Some suggestive features present - keep amyloidosis in the differential, particularly if proteinuria doesn't fit a more common cause.", "severity": "caution"})
        return {
            "headline": f"{len(clues)} multi-organ clue(s) present", "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Amyloidosis is a multi-system disease; renal involvement (often heavy proteinuria) plus clues elsewhere (cardiac, neurologic, hepatic) raise suspicion. This checklist is a screening aid - diagnosis requires tissue biopsy with Congo red staining (and typing, e.g., mass spectrometry, to distinguish AL vs. AA vs. hereditary forms).",
        }


class AntiGBMDiseaseCalculator(Calculator):
    key = "anti_gbm_disease"

    def compute(self, a: dict) -> dict:
        meets_diagnosis = (a.get("antiGbmAntibodyPositive") == "yes" or a.get("linearIgGOnBiopsy") == "yes") and (a.get("rpgn") == "yes" or a.get("pulmonaryHemorrhage") == "yes")
        flags = []
        if meets_diagnosis:
            flags.append({"text": "Meets the classic diagnostic pattern for anti-GBM disease - initiate urgent plasma exchange plus immunosuppression (cyclophosphamide + glucocorticoids); early treatment before dialysis-dependence is the key driver of renal recovery.", "severity": "critical"})
        if a.get("pulmonaryHemorrhage") == "yes":
            flags.append({"text": "Pulmonary hemorrhage is a medical emergency - may require mechanical ventilation and should not delay urgent plasma exchange.", "severity": "critical"})
        if a.get("ancaAlsoPositive") == "yes":
            flags.append({"text": "Dual ANCA/anti-GBM positivity occurs in a meaningful minority of cases and may follow a somewhat different course - treat as anti-GBM disease but monitor for vasculitic features too.", "severity": "caution"})
        return {
            "headline": "Meets diagnostic criteria for anti-GBM disease" if meets_diagnosis else "Criteria not fully met",
            "headlineSeverity": "critical" if meets_diagnosis else "caution",
            "metrics": [], "flags": flags,
            "notes": "Based on the classic anti-GBM (Goodpasture) disease pattern: circulating and/or tissue-bound anti-GBM antibodies plus rapidly progressive glomerulonephritis and/or pulmonary hemorrhage.",
        }


class AHUSTTPDifferentiationCalculator(Calculator):
    key = "ahus_ttp_differentiation"

    def compute(self, a: dict) -> dict:
        flags = []
        triggers_all = _list(a.get("triggeringEvent"))
        if a.get("adamts13Activity") == "severely reduced (<10%)":
            headline, sev = "Pattern favors TTP (severe ADAMTS13 deficiency)", "critical"
            flags.append({"text": "Initiate urgent plasma exchange for suspected/confirmed TTP; don't delay for the full confirmatory workup if clinical suspicion is high (see also the PLASMIC Score module).", "severity": "critical"})
        elif "infection-diarrhea-associated" in triggers_all:
            headline, sev = "Pattern favors Shiga-toxin-associated HUS (STEC-HUS)", "warning"
            flags.append({"text": "Supportive care is the mainstay; avoid antibiotics and antimotility agents in suspected STEC infection, and avoid plasma exchange unless another process is also suspected.", "severity": "warning"})
        elif a.get("adamts13Activity") in ("normal or mildly reduced", "not tested"):
            triggers = [t for t in triggers_all if t not in ("none", "infection-diarrhea-associated")]
            if triggers or a.get("renalFailureSeverity") == "severe":
                headline, sev = "Pattern favors atypical HUS (complement-mediated)", "warning"
                flags.append({"text": "Consider complement pathway studies (C3, C4, factor H/I, anti-factor H antibodies, genetic panel) and discuss complement inhibitor therapy (e.g., eculizumab) with a specialist center.", "severity": "warning"})
            else:
                headline, sev = "Pattern not yet clearly differentiated", "caution"
        else:
            headline, sev = "Pattern not yet clearly differentiated", "caution"
        flags.append({"text": "ADAMTS13 activity is the single most discriminating test - send urgently if not already done, and don't let a normal platelet count alone rule out TMA.", "severity": "caution"})
        plt = _num_or_none(a.get("plateletCount"))
        return {
            "headline": headline, "headlineSeverity": sev,
            "metrics": [{"label": "Platelets", "value": plt if plt is not None else "\u2014", "unit": "\u00d710\u2079/L"}], "flags": flags,
            "notes": "A structured differentiator among the thrombotic microangiopathies (TTP, STEC-HUS, atypical HUS) - real cases can overlap, and definitive diagnosis relies on ADAMTS13 activity and, where relevant, Shiga toxin/PCR testing and complement studies. This complements the PLASMIC Score module rather than replacing it.",
        }


class HIVAssociatedNephropathyCalculator(Calculator):
    key = "hiv_associated_nephropathy"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        if a.get("proteinuriaPresent") == "yes" and a.get("hivViralLoadSuppressed") == "no":
            flags.append({"text": "Proteinuria with uncontrolled HIV raises concern for HIV-associated nephropathy (HIVAN) - classic collapsing FSGS pattern; ART initiation/optimization is itself a key treatment.", "severity": "warning"})
            sev = "warning"
        if a.get("onArt") == "no":
            flags.append({"text": "Not on ART - starting/optimizing antiretroviral therapy is the single most important intervention for HIVAN and related HIV kidney diseases.", "severity": "warning"})
            sev = "warning"
        if a.get("apol1HighRisk") == "yes":
            flags.append({"text": "APOL1 high-risk genotype substantially increases HIVAN risk in the setting of uncontrolled HIV - see the APOL1 Genetic Risk module.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if a.get("proteinuriaPresent") == "yes":
            flags.append({"text": "Consider renal biopsy if proteinuria is significant and the diagnosis is unclear - HIVAN, HIV immune-complex kidney disease, and unrelated glomerular diseases can look similar clinically.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        egfr = _num_or_none(a.get("egfr"))
        return {
            "headline": f"{len(flags)} item(s) flagged" if flags else "No concerns flagged from entries",
            "headlineSeverity": sev,
            "metrics": [{"label": "eGFR", "value": egfr, "unit": "mL/min/1.73m\u00b2"}] if egfr is not None else [], "flags": flags,
            "notes": "HIVAN classically presents as collapsing FSGS with heavy proteinuria in patients with uncontrolled HIV, disproportionately among those with APOL1 high-risk genotypes. ART is both preventive and therapeutic; biopsy distinguishes HIVAN from other HIV-associated kidney diseases.",
        }


class C3GlomerulopathyCalculator(Calculator):
    key = "c3_glomerulopathy"

    def compute(self, a: dict) -> dict:
        if a.get("c3DominantStaining") != "yes":
            return {
                "headline": "Does not meet C3-dominant staining criterion", "headlineSeverity": "caution", "metrics": [],
                "flags": [{"text": "C3 glomerulopathy requires C3-dominant staining on immunofluorescence - without this, consider other causes of the glomerular pattern (e.g., post-infectious GN, immune-complex GN).", "severity": "caution"}],
                "notes": "",
            }
        subtype = "Dense deposit disease" if a.get("denseDepositsOnEM") == "yes" else "C3 glomerulonephritis"
        abnormalities = [x for x in _list(a.get("complementAbnormality")) if x != "none"]
        flags = [{"text": f"Subtype: {subtype} (based on electron microscopy findings).", "severity": "caution"}]
        if abnormalities:
            flags.append({"text": f"Complement abnormality identified ({', '.join(abnormalities)}) - supports a complement-dysregulation-driven process; consider a complement inhibitor trial (e.g., eculizumab) in refractory cases, ideally guided by a specialist center.", "severity": "warning"})
        else:
            flags.append({"text": "No complement abnormality identified yet - a full complement pathway workup (C3, C4, factor H/I/B, C3 nephritic factor, genetic panel) is recommended even if initial studies are normal.", "severity": "caution"})
        return {
            "headline": f"{subtype} pattern", "headlineSeverity": "warning", "metrics": [], "flags": flags,
            "notes": "C3 glomerulopathy is defined by C3-dominant immunofluorescence staining, with dense deposit disease vs. C3 glomerulonephritis distinguished by electron microscopy. A thorough complement pathway workup is recommended regardless of initial results, since abnormalities aren't always found on first-line testing.",
        }
