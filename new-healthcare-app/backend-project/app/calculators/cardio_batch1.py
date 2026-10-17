import math
from app.calculators.base import Calculator


def _num_or_none(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


class NYHACalculator(Calculator):
    key = "nyha"

    def compute(self, a: dict) -> dict:
        if not a.get("cls"):
            return {"headline": "Select a symptom level to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        labels = {"1": "Class I", "2": "Class II", "3": "Class III", "4": "Class IV"}
        sev_map = {"1": "good", "2": "caution", "3": "warning", "4": "critical"}
        cls = a["cls"]
        return {
            "headline": f"NYHA {labels[cls]}",
            "headlineSeverity": sev_map[cls],
            "metrics": [{"label": "NYHA class", "value": labels[cls]}],
            "flags": [{"text": "Marked-to-severe functional limitation - reassess guideline-directed medical therapy and consider advanced therapies referral", "severity": sev_map[cls]}] if int(cls) >= 3 else [],
            "notes": "A symptom-based classification, not a direct measure of ejection fraction or hemodynamics - correlate with objective testing.",
        }


class KillipCalculator(Calculator):
    key = "killip"

    def compute(self, a: dict) -> dict:
        if not a.get("cls"):
            return {"headline": "Select a clinical presentation to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        labels = {"1": "Class I", "2": "Class II", "3": "Class III", "4": "Class IV"}
        sev_map = {"1": "good", "2": "caution", "3": "warning", "4": "critical"}
        cls = a["cls"]
        return {
            "headline": f"Killip {labels[cls]}",
            "headlineSeverity": sev_map[cls],
            "metrics": [{"label": "Killip class", "value": labels[cls]}],
            "flags": [{"text": "High-risk presentation historically associated with substantially increased in-hospital mortality - consider escalation of care", "severity": sev_map[cls]}] if int(cls) >= 3 else [],
            "notes": "Historically derived mortality estimates per class vary by era and population - verify against current outcomes data rather than relying on classification alone.",
        }


class TIMIUnstableCalculator(Calculator):
    key = "timi_unstable"

    def compute(self, a: dict) -> dict:
        fields = ["age65", "riskFactors", "knownCad", "aspirin", "severeAngina", "stChange", "biomarkers"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 7 items to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        score = sum(1 for f in fields if a.get(f) == "yes")
        if score <= 1:
            sev, band = "good", "low"
        elif score <= 3:
            sev, band = "caution", "low-to-intermediate"
        elif score <= 4:
            sev, band = "warning", "intermediate-to-high"
        else:
            sev, band = "critical", "high"
        return {
            "headline": f"TIMI = {score} - {band} risk of adverse cardiac events within 14 days.",
            "headlineSeverity": sev,
            "metrics": [{"label": "TIMI score", "value": score, "unit": "/ 7"}],
            "flags": [{"text": "Elevated TIMI score - supports early invasive strategy per guideline-directed care", "severity": sev}] if score >= 3 else [],
            "notes": "Risk-band cut points are commonly cited approximations - verify exact event-rate percentages against current source literature before using for risk disclosure.",
        }


class QTcBazettCalculator(Calculator):
    key = "qtc_bazett"

    def compute(self, a: dict) -> dict:
        qt, hr = _num_or_none(a.get("qt")), _num_or_none(a.get("hr"))
        if qt is None or hr is None or hr <= 0:
            return {"headline": "Enter QT interval and heart rate to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        rr_sec = 60 / hr
        qtc = qt / math.sqrt(rr_sec)
        upper_limit = 460 if a.get("sex") == "female" else 450
        if qtc > 500:
            sev, headline = "critical", f"QTc approximately {qtc:.0f} ms - markedly prolonged, elevated torsades risk."
        elif qtc > upper_limit:
            sev, headline = "warning", f"QTc approximately {qtc:.0f} ms - prolonged for stated sex."
        else:
            sev, headline = "good", f"QTc approximately {qtc:.0f} ms - within commonly cited normal range."
        return {
            "headline": headline,
            "headlineSeverity": sev,
            "metrics": [{"label": "QTc (Bazett)", "value": f"{qtc:.0f}", "unit": "ms"}],
            "flags": [{"text": "Review QT-prolonging medications and correct electrolyte abnormalities (potassium, magnesium, calcium)", "severity": "critical"}] if qtc > 500 else [],
            "notes": "The Bazett correction is the most widely used but is known to overcorrect at heart rates far from 60 bpm - consider the Fridericia correction for extremes of heart rate. Normal thresholds shown are commonly cited approximations; verify locally.",
        }


class HEARTScoreCalculator(Calculator):
    key = "heart_score"

    def compute(self, a: dict) -> dict:
        age = _num_or_none(a.get("age"))
        if age is None or not a.get("history") or not a.get("ecg") or not a.get("riskFactors") or not a.get("troponin"):
            return {"headline": "Answer all 5 components to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        age_score = 2 if age >= 65 else (1 if age >= 45 else 0)
        score = int(a["history"]) + int(a["ecg"]) + age_score + int(a["riskFactors"]) + int(a["troponin"])
        if score <= 3:
            sev, band = "good", "low"
        elif score <= 6:
            sev, band = "warning", "moderate"
        else:
            sev, band = "critical", "high"
        flags = []
        if score >= 7:
            flags.append({"text": "High-risk HEART score - early invasive strategy and admission typically warranted", "severity": "critical"})
        elif score >= 4:
            flags.append({"text": "Moderate-risk HEART score - further risk stratification (serial troponins, stress testing, or observation) generally warranted", "severity": "warning"})
        return {
            "headline": f"HEART score = {score} - {band} risk of major adverse cardiac events at 6 weeks.",
            "headlineSeverity": sev,
            "metrics": [{"label": "HEART score", "value": score, "unit": "/ 10"}, {"label": "Age component", "value": age_score, "unit": "pts"}],
            "flags": flags,
            "notes": "Risk-band event-rate percentages are commonly cited approximations - verify exact figures against current source literature before disclosing precise risk numbers to a patient.",
        }


class HFStagingCalculator(Calculator):
    key = "hf_staging"

    def compute(self, a: dict) -> dict:
        if not a.get("structural") or not a.get("symptoms") or not a.get("refractory"):
            return {"headline": "Answer all 3 items to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if a["refractory"] == "yes":
            stage, sev = "D", "critical"
        elif a["symptoms"] == "yes":
            stage, sev = "C", "warning"
        elif a["structural"] == "yes":
            stage, sev = "B", "caution"
        else:
            stage, sev = "A", "good"
        desc = {
            "A": "At risk for heart failure, no structural disease or symptoms yet",
            "B": "Structural heart disease present, no current or prior symptoms",
            "C": "Structural heart disease with current or prior heart failure symptoms",
            "D": "Refractory heart failure requiring specialized intervention",
        }
        return {
            "headline": f"ACC/AHA Stage {stage} - {desc[stage]}",
            "headlineSeverity": sev,
            "metrics": [{"label": "HF stage", "value": f"Stage {stage}"}],
            "flags": [{"text": "Refractory heart failure - consider advanced therapies referral (transplant, mechanical support, or palliative care)", "severity": "critical"}] if stage == "D" else [],
            "notes": "A progression-based staging system, distinct from NYHA functional class - a patient can move between NYHA classes within the same stage but does not move backward between stages.",
        }


class EFClassificationCalculator(Calculator):
    key = "ef_classification"

    def compute(self, a: dict) -> dict:
        ef = _num_or_none(a.get("ef"))
        if ef is None:
            return {"headline": "Enter ejection fraction to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if ef <= 40:
            label, sev = "HFrEF (reduced ejection fraction)", "warning"
        elif ef <= 49:
            label, sev = "HFmrEF (mildly reduced ejection fraction)", "caution"
        else:
            label, sev = "HFpEF (preserved ejection fraction)", "caution"
        return {
            "headline": f"EF {ef}% - {label}",
            "headlineSeverity": sev,
            "metrics": [{"label": "Ejection fraction", "value": ef, "unit": "%"}],
            "flags": [{"text": "HFrEF - guideline-directed medical therapy (ARNI/ACEi/ARB, beta-blocker, MRA, SGLT2 inhibitor) indicated if not already optimized", "severity": "warning"}] if ef <= 40 else [],
            "notes": "Category thresholds reflect commonly cited guideline cut points; management differs meaningfully across the three phenotypes, particularly for HFpEF where evidence for traditional HFrEF therapies is more limited.",
        }


class ABICalculator(Calculator):
    key = "abi_calc"

    def compute(self, a: dict) -> dict:
        ankle, arm = _num_or_none(a.get("ankleSbp")), _num_or_none(a.get("armSbp"))
        if ankle is None or arm is None or arm <= 0:
            return {"headline": "Enter ankle and arm systolic pressures to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        abi = ankle / arm
        if abi > 1.40:
            sev, label = "caution", "non-compressible vessels, result unreliable - consider toe-brachial index"
        elif abi >= 1.00:
            sev, label = "good", "normal"
        elif abi >= 0.91:
            sev, label = "caution", "borderline"
        elif abi >= 0.41:
            sev, label = "warning", "mild-to-moderate peripheral arterial disease"
        else:
            sev, label = "critical", "severe peripheral arterial disease"
        return {
            "headline": f"ABI = {abi:.2f} - {label}.",
            "headlineSeverity": sev,
            "metrics": [{"label": "ABI", "value": f"{abi:.2f}"}],
            "flags": [{"text": "ABI below 0.90 supports a diagnosis of peripheral arterial disease - consider vascular referral", "severity": "critical" if abi < 0.41 else "warning"}] if abi < 0.90 else [],
            "notes": "Calcified, non-compressible vessels (common in diabetes and advanced CKD) can falsely elevate ABI above 1.40 - correlate with clinical exam and consider toe-brachial index in that setting.",
        }


class BPCategoryCalculator(Calculator):
    key = "bp_category"

    def compute(self, a: dict) -> dict:
        sbp, dbp = _num_or_none(a.get("sbp")), _num_or_none(a.get("dbp"))
        if sbp is None or dbp is None:
            return {"headline": "Enter systolic and diastolic BP to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if sbp > 180 or dbp > 120:
            label, sev = "Hypertensive crisis", "critical"
        elif sbp >= 140 or dbp >= 90:
            label, sev = "Stage 2 hypertension", "warning"
        elif sbp >= 130 or dbp >= 80:
            label, sev = "Stage 1 hypertension", "caution"
        elif sbp >= 120:
            label, sev = "Elevated", "caution"
        else:
            label, sev = "Normal", "good"
        return {
            "headline": f"{sbp:g}/{dbp:g} mmHg - {label}.",
            "headlineSeverity": sev,
            "metrics": [{"label": "Category", "value": label}],
            "flags": [{"text": "Hypertensive crisis - assess for end-organ damage and need for urgent or emergent treatment", "severity": "critical"}] if label == "Hypertensive crisis" else [],
            "notes": "Category cut points reflect commonly cited ACC/AHA guideline thresholds - if systolic and diastolic values fall into different categories, the higher category generally applies.",
        }


class RCRICalculator(Calculator):
    key = "rcri"

    def compute(self, a: dict) -> dict:
        fields = ["highRiskSurgery", "ischemicHeart", "chf", "cerebrovascular", "insulin", "renal"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 6 items to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        score = sum(1 for f in fields if a.get(f) == "yes")
        if score == 0:
            sev, cls = "good", "Class I"
        elif score == 1:
            sev, cls = "caution", "Class II"
        elif score == 2:
            sev, cls = "warning", "Class III"
        else:
            sev, cls = "critical", "Class IV"
        return {
            "headline": f"RCRI = {score} factor(s) - {cls}, {'elevated' if score >= 2 else 'lower'} risk of major cardiac complications after noncardiac surgery.",
            "headlineSeverity": sev,
            "metrics": [{"label": "RCRI factors present", "value": score, "unit": "/ 6"}],
            "flags": [{"text": "High RCRI class - consider cardiology consultation and further preoperative risk assessment before elective noncardiac surgery", "severity": "critical"}] if score >= 3 else [],
            "notes": "One of the 6 factors reflects renal function (creatinine above 2.0 mg/dL) - a genuine point of overlap between cardiac and kidney risk in the perioperative setting. Risk-percentage estimates per class are commonly cited approximations - verify against current source literature.",
        }


class AorticStenosisCalculator(Calculator):
    key = "aortic_stenosis"

    def compute(self, a: dict) -> dict:
        v, g, va = _num_or_none(a.get("peakVelocity")), _num_or_none(a.get("meanGradient")), _num_or_none(a.get("valveArea"))
        if v is None and g is None and va is None:
            return {"headline": "Enter at least one echocardiographic parameter to grade severity.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        grades = []
        if v is not None:
            grades.append("severe" if v >= 4.0 else ("moderate" if v >= 3.0 else "mild"))
        if g is not None:
            grades.append("severe" if g >= 40 else ("moderate" if g >= 20 else "mild"))
        if va is not None:
            grades.append("severe" if va < 1.0 else ("moderate" if va <= 1.5 else "mild"))
        order = {"mild": 1, "moderate": 2, "severe": 3}
        worst = max(grades, key=lambda x: order[x])
        sev_map = {"mild": "caution", "moderate": "warning", "severe": "critical"}
        return {
            "headline": f"Aortic stenosis: {worst} (based on {len(grades)} parameter{'s' if len(grades) != 1 else ''} entered).",
            "headlineSeverity": sev_map[worst],
            "metrics": [{"label": "Parameters entered", "value": len(grades)}],
            "flags": [{"text": "Severe aortic stenosis - evaluate for symptoms and consider valve intervention (SAVR/TAVR) per guideline criteria", "severity": "critical"}] if worst == "severe" else [],
            "notes": "Parameters can be discordant (e.g. low-flow, low-gradient severe AS with preserved valve area) - this reports the single worst parameter entered, which does not replace integrated echocardiographic and clinical assessment.",
        }


class MitralRegurgitationCalculator(Calculator):
    key = "mitral_regurgitation"

    def compute(self, a: dict) -> dict:
        vc = _num_or_none(a.get("venaContracta"))
        if vc is None:
            return {"headline": "Enter vena contracta width to grade severity.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if vc >= 7:
            sev, label = "critical", "severe"
        elif vc >= 3:
            sev, label = "warning", "moderate"
        else:
            sev, label = "caution", "mild"
        return {
            "headline": f"Mitral regurgitation: {label} (vena contracta {vc:g} mm).",
            "headlineSeverity": sev,
            "metrics": [{"label": "Vena contracta", "value": vc, "unit": "mm"}],
            "flags": [{"text": "Severe MR - assess symptoms and LV function; consider surgical or transcatheter repair per guideline criteria", "severity": "critical"}] if label == "severe" else [],
            "notes": "Vena contracta is one of several echocardiographic parameters used to grade MR (alongside regurgitant volume, effective regurgitant orifice area, and jet characteristics) - integrated multi-parametric assessment is standard practice, not a single measurement in isolation.",
        }


class SFSRCalculator(Calculator):
    key = "sfsr"

    def compute(self, a: dict) -> dict:
        fields = ["chf", "hematocrit", "ecg", "sob", "sbp"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 5 criteria to screen.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        any_positive = any(a.get(f) == "yes" for f in fields)
        return {
            "headline": "Positive screen - higher risk of a serious short-term outcome." if any_positive else "Negative screen - lower risk of a serious short-term outcome.",
            "headlineSeverity": "critical" if any_positive else "good",
            "metrics": [{"label": "Criteria positive", "value": sum(1 for f in fields if a.get(f) == "yes"), "unit": "/ 5"}],
            "flags": [{"text": "Any single positive criterion classifies as high risk - consider admission or further urgent workup", "severity": "critical"}] if any_positive else [],
            "notes": "Unlike additive risk scores, this rule flags high risk if ANY ONE criterion is positive - a screening rule, not a substitute for full clinical judgment.",
        }


class PericarditisCalculator(Calculator):
    key = "pericarditis"

    def compute(self, a: dict) -> dict:
        fields = ["chestPain", "rub", "ecgChanges", "effusion"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 4 criteria to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        met = count >= 2
        return {
            "headline": f"{count} of 4 criteria met - diagnostic criteria for acute pericarditis satisfied." if met else f"{count} of 4 criteria met - diagnostic criteria not satisfied.",
            "headlineSeverity": "warning" if met else "good",
            "metrics": [{"label": "Criteria met", "value": count, "unit": "/ 4"}],
            "flags": [{"text": "Evaluate for underlying cause and high-risk features (fever, large effusion, immunosuppression, failure to respond to NSAIDs) that would warrant admission", "severity": "warning"}] if met else [],
            "notes": "Requires at least 2 of these 4 findings - does not replace assessment for an underlying cause (viral, autoimmune, uremic, post-MI, malignant, etc.). Uremic pericarditis is a recognized complication of advanced kidney failure, worth considering in that population.",
        }


class CardiomyopathyTypeCalculator(Calculator):
    key = "cardiomyopathy_type"

    def compute(self, a: dict) -> dict:
        if not a.get("cmType"):
            return {"headline": "Select a cardiomyopathy type to see relevant considerations.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        notes = {
            "dilated": "Dilated cardiomyopathy typically presents with LV enlargement and reduced systolic function - evaluate for reversible causes (ischemia, alcohol, tachycardia-mediated, peripartum, toxin or chemotherapy-related) alongside standard HFrEF therapy.",
            "hypertrophic": "Hypertrophic cardiomyopathy carries sudden cardiac death risk - consider a dedicated SCD risk assessment, family screening and genetic counseling, and avoidance of extreme exertion pending evaluation.",
            "restrictive": "Restrictive cardiomyopathy can mimic constrictive pericarditis - evaluate for infiltrative causes (amyloidosis, sarcoidosis, hemochromatosis), some of which have specific disease-modifying therapies.",
            "arrhythmogenic": "Arrhythmogenic right ventricular cardiomyopathy carries significant ventricular arrhythmia risk - evaluate for ICD candidacy and screen first-degree relatives.",
        }
        labels = {"dilated": "Dilated", "hypertrophic": "Hypertrophic", "restrictive": "Restrictive", "arrhythmogenic": "Arrhythmogenic (right ventricular)"}
        cm_type = a["cmType"]
        return {
            "headline": f"{labels[cm_type]} cardiomyopathy recorded.",
            "headlineSeverity": "caution",
            "metrics": [{"label": "Type", "value": labels[cm_type]}],
            "flags": [],
            "notes": notes[cm_type],
        }


class ACHDComplexityCalculator(Calculator):
    key = "achd_complexity"

    def compute(self, a: dict) -> dict:
        if not a.get("complexity"):
            return {"headline": "Select a complexity level to see follow-up considerations.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        info = {
            "simple": {"label": "Simple congenital heart disease", "sev": "good", "note": "Generally followed at intervals by cardiology; pregnancy and noncardiac surgery risk is usually low but should still be confirmed on an individual basis."},
            "moderate": {"label": "Moderate-complexity congenital heart disease", "sev": "warning", "note": "Typically requires ongoing specialized, ideally ACHD-trained, cardiology follow-up; pregnancy and surgical risk assessment should be individualized."},
            "complex": {"label": "Complex congenital heart disease", "sev": "critical", "note": "Should be managed at or in close consultation with a specialized ACHD center; pregnancy is often high-risk or contraindicated depending on the specific lesion, and noncardiac surgery requires careful multidisciplinary planning."},
        }
        c = info[a["complexity"]]
        return {
            "headline": f"{c['label']} recorded.",
            "headlineSeverity": c["sev"],
            "metrics": [{"label": "Complexity", "value": a["complexity"].capitalize()}],
            "flags": [{"text": "Complex ACHD - confirm active follow-up with a specialized ACHD center", "severity": "critical"}] if a["complexity"] == "complex" else [],
            "notes": c["note"],
        }


class MWHOClassificationCalculator(Calculator):
    key = "mwho_classification"

    def compute(self, a: dict) -> dict:
        if not a.get("mwhoClass"):
            return {"headline": "Select an mWHO class to see risk-level guidance.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        info = {
            "1": {"label": "mWHO Class I", "sev": "good", "note": "No detectable increased maternal risk - standard obstetric follow-up is generally appropriate, with at least one cardiology assessment during pregnancy."},
            "2": {"label": "mWHO Class II", "sev": "caution", "note": "Small increased risk - cardiology and obstetric follow-up each trimester is generally recommended."},
            "2-3": {"label": "mWHO Class II-III", "sev": "warning", "note": "Intermediate risk - more frequent cardiology and obstetric follow-up (monthly or bimonthly) is generally recommended, ideally at a center with expertise in cardiac disease in pregnancy."},
            "3": {"label": "mWHO Class III", "sev": "warning", "note": "Significantly increased risk of maternal morbidity or mortality - care at a specialized pregnancy heart team center is generally recommended, with frequent (monthly or more) follow-up."},
            "4": {"label": "mWHO Class IV", "sev": "critical", "note": "Pregnancy is generally considered contraindicated at this risk level - if pregnancy occurs or continues, care should involve a specialized pregnancy heart team, and termination should be discussed."},
        }
        c = info[a["mwhoClass"]]
        return {
            "headline": f"{c['label']} recorded.",
            "headlineSeverity": c["sev"],
            "metrics": [{"label": "mWHO class", "value": c["label"].replace("mWHO ", "")}],
            "flags": [{"text": "High-risk mWHO class - ensure care involves a specialized pregnancy heart team", "severity": "critical"}] if a["mwhoClass"] in ("3", "4") else [],
            "notes": c["note"],
        }


class OrthostaticHypotensionCalculator(Calculator):
    key = "orthostatic_hypotension"

    def compute(self, a: dict) -> dict:
        ssbp, sdbp = _num_or_none(a.get("supineSbp")), _num_or_none(a.get("supineDbp"))
        tsbp, tdbp = _num_or_none(a.get("standingSbp")), _num_or_none(a.get("standingDbp"))
        if ssbp is None or sdbp is None or tsbp is None or tdbp is None:
            return {"headline": "Enter all 4 blood pressure values to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        sbp_drop = ssbp - tsbp
        dbp_drop = sdbp - tdbp
        positive = sbp_drop >= 20 or dbp_drop >= 10
        return {
            "headline": f"Orthostatic hypotension present (SBP drop {sbp_drop:g} mmHg, DBP drop {dbp_drop:g} mmHg)." if positive else f"No orthostatic hypotension by standard criteria (SBP drop {sbp_drop:g} mmHg, DBP drop {dbp_drop:g} mmHg).",
            "headlineSeverity": "warning" if positive else "good",
            "metrics": [{"label": "SBP drop", "value": sbp_drop, "unit": "mmHg"}, {"label": "DBP drop", "value": dbp_drop, "unit": "mmHg"}],
            "flags": [{"text": "Consider medication review (antihypertensives, diuretics), volume status, and autonomic causes", "severity": "warning"}] if positive else [],
            "notes": "Standard criteria: a drop of 20 mmHg or more in systolic BP, or 10 mmHg or more in diastolic BP, within 3 minutes of standing. Measure at both 1 and 3 minutes when possible - later drops can be missed with a single reading.",
        }


class ADDRSCalculator(Calculator):
    key = "add_rs"

    def compute(self, a: dict) -> dict:
        fields = ["highRiskConditions", "highRiskPain", "highRiskExam"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 3 categories to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        score = sum(1 for f in fields if a.get(f) == "yes")
        if score == 0:
            sev, band = "good", "low"
        elif score == 1:
            sev, band = "caution", "low-to-intermediate"
        else:
            sev, band = "critical", "high"
        return {
            "headline": f"ADD-RS = {score} - {band} risk category for acute aortic syndrome.",
            "headlineSeverity": sev,
            "metrics": [{"label": "ADD-RS", "value": score, "unit": "/ 3"}],
            "flags": [{"text": "ADD-RS of 1 or more generally supports further workup (D-dimer if score is 1, direct imaging with CT/MR/TEE if score is 2 or higher) per commonly cited chest pain pathways", "severity": "critical" if score >= 2 else "caution"}] if score >= 1 else [],
            "notes": "Score reflects the number of the 3 categories with at least one positive feature, not a simple count of individual items - verify current institutional pathway thresholds, as exact D-dimer and imaging cutoffs vary.",
        }


class AFibTypeCalculator(Calculator):
    key = "afib_type"

    def compute(self, a: dict) -> dict:
        if not a.get("pattern"):
            return {"headline": "Select a temporal pattern to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        labels = {"paroxysmal": "Paroxysmal", "persistent": "Persistent", "longstanding": "Long-standing persistent", "permanent": "Permanent"}
        notes = {
            "paroxysmal": "Rhythm-control strategies (antiarrhythmics, ablation) are often more successful at this stage.",
            "persistent": "May still be a candidate for rhythm control (cardioversion, ablation) depending on symptoms and shared decision-making.",
            "longstanding": "Rhythm control is still sometimes pursued but success rates are generally lower - rate control and anticoagulation remain foundational regardless of strategy.",
            "permanent": "By definition, further rhythm-control attempts have been jointly abandoned - focus shifts to rate control and anticoagulation.",
        }
        pattern = a["pattern"]
        return {
            "headline": f"{labels[pattern]} atrial fibrillation recorded.",
            "headlineSeverity": "caution",
            "metrics": [{"label": "Pattern", "value": labels[pattern]}],
            "flags": [],
            "notes": notes[pattern] + " Anticoagulation decisions are based on stroke risk (CHA2DS2-VASc), not on AF pattern or symptom burden.",
        }


class AVBlockCalculator(Calculator):
    key = "av_block"

    def compute(self, a: dict) -> dict:
        if not a.get("degree"):
            return {"headline": "Select an AV block degree to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        info = {
            "first": {"label": "First-degree AV block", "sev": "good", "note": "Usually benign and asymptomatic - pacing is rarely indicated for first-degree block alone."},
            "mobitz1": {"label": "Second-degree AV block, Mobitz type I", "sev": "caution", "note": "Usually benign, often due to increased vagal tone - pacing is generally reserved for symptomatic patients."},
            "mobitz2": {"label": "Second-degree AV block, Mobitz type II", "sev": "warning", "note": "Higher risk of progression to complete heart block - pacing is generally indicated regardless of symptoms."},
            "third": {"label": "Third-degree (complete) AV block", "sev": "critical", "note": "Generally requires pacing - assess hemodynamic stability urgently and evaluate for reversible causes (ischemia, medication effect, electrolyte abnormality) before permanent pacemaker placement."},
        }
        c = info[a["degree"]]
        return {
            "headline": f"{c['label']} recorded.",
            "headlineSeverity": c["sev"],
            "metrics": [{"label": "AV block degree", "value": c["label"]}],
            "flags": [{"text": "Pacing is generally indicated - evaluate hemodynamic stability and reversible causes", "severity": c["sev"]}] if a["degree"] in ("mobitz2", "third") else [],
            "notes": c["note"],
        }


class MitralStenosisCalculator(Calculator):
    key = "mitral_stenosis"

    def compute(self, a: dict) -> dict:
        va, g = _num_or_none(a.get("valveArea")), _num_or_none(a.get("meanGradient"))
        if va is None and g is None:
            return {"headline": "Enter at least one echocardiographic parameter to grade severity.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        grades = []
        if va is not None:
            grades.append("severe" if va < 1.5 else ("moderate" if va <= 2.0 else "mild"))
        if g is not None:
            grades.append("severe" if g > 10 else ("moderate" if g >= 5 else "mild"))
        order = {"mild": 1, "moderate": 2, "severe": 3}
        worst = max(grades, key=lambda x: order[x])
        sev_map = {"mild": "caution", "moderate": "warning", "severe": "critical"}
        return {
            "headline": f"Mitral stenosis: {worst} (based on {len(grades)} parameter{'s' if len(grades) != 1 else ''} entered).",
            "headlineSeverity": sev_map[worst],
            "metrics": [{"label": "Parameters entered", "value": len(grades)}],
            "flags": [{"text": "Severe mitral stenosis - assess symptoms and consider balloon valvuloplasty or surgical intervention per guideline criteria", "severity": "critical"}] if worst == "severe" else [],
            "notes": "Valve area and gradient can be discordant, especially with abnormal flow states - integrated echocardiographic assessment (including pressure half-time and pulmonary pressures) is standard practice, not a single measurement in isolation.",
        }


class TricuspidRegurgitationCalculator(Calculator):
    key = "tricuspid_regurgitation"

    def compute(self, a: dict) -> dict:
        vc = _num_or_none(a.get("venaContracta"))
        if vc is None:
            return {"headline": "Enter vena contracta width to grade severity.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if vc >= 7:
            sev, label = "critical", "severe"
        elif vc >= 3:
            sev, label = "warning", "moderate"
        else:
            sev, label = "caution", "mild"
        return {
            "headline": f"Tricuspid regurgitation: {label} (vena contracta {vc:g} mm).",
            "headlineSeverity": sev,
            "metrics": [{"label": "Vena contracta", "value": vc, "unit": "mm"}],
            "flags": [{"text": "Severe TR - assess right ventricular size and function, and consider surgical timing before irreversible RV dysfunction develops", "severity": "critical"}] if label == "severe" else [],
            "notes": "Severe TR is often under-recognized and undertreated - right heart size/function trends matter as much as the regurgitation grade itself when considering intervention timing.",
        }


class CHDLesionReferenceCalculator(Calculator):
    key = "chd_lesion_reference"

    def compute(self, a: dict) -> dict:
        if not a.get("lesion"):
            return {"headline": "Select a lesion to see follow-up considerations.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        notes = {
            "asd": "Unrepaired ASDs with significant shunt can lead to right heart enlargement and pulmonary hypertension over time - closure is generally considered for significant shunts even if asymptomatic.",
            "vsd": "Small, restrictive VSDs are often followed without intervention - larger or unrepaired defects carry risk of pulmonary hypertension and Eisenmenger physiology if left untreated.",
            "pda": "Small PDAs may be followed clinically - larger shunts or evidence of left heart volume overload generally warrant closure.",
            "coarctation": "Even after repair, recurrent or residual coarctation and associated hypertension require ongoing surveillance - check for differential blood pressures between arms and legs at follow-up.",
            "tof": "After repair, longitudinal surveillance for pulmonary regurgitation, right ventricular enlargement/dysfunction, and arrhythmia is standard - many patients eventually need pulmonary valve replacement.",
        }
        labels = {"asd": "Atrial septal defect", "vsd": "Ventricular septal defect", "pda": "Patent ductus arteriosus", "coarctation": "Coarctation of the aorta", "tof": "Tetralogy of Fallot (repaired)"}
        lesion = a["lesion"]
        return {
            "headline": f"{labels[lesion]} recorded.",
            "headlineSeverity": "caution",
            "metrics": [{"label": "Lesion", "value": labels[lesion]}],
            "flags": [],
            "notes": notes[lesion],
        }


class WellsPECalculator(Calculator):
    key = "wells_pe"

    def compute(self, a: dict) -> dict:
        fields = ["dvtSigns", "peMostLikely", "heartRate", "immobilization", "priorDvtPe", "hemoptysis", "malignancy"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 7 items to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        score = 0
        if a.get("dvtSigns") == "yes":
            score += 3
        if a.get("peMostLikely") == "yes":
            score += 3
        if a.get("heartRate") == "yes":
            score += 1.5
        if a.get("immobilization") == "yes":
            score += 1.5
        if a.get("priorDvtPe") == "yes":
            score += 1.5
        if a.get("hemoptysis") == "yes":
            score += 1
        if a.get("malignancy") == "yes":
            score += 1
        pe_likely = score > 4
        return {
            "headline": f"Wells score = {score:g} - PE {'likely' if pe_likely else 'unlikely'} by the simplified dichotomized interpretation.",
            "headlineSeverity": "critical" if pe_likely else "caution",
            "metrics": [{"label": "Wells score", "value": score}],
            "flags": [{"text": "PE likely - proceed directly to imaging (CT pulmonary angiography) rather than D-dimer", "severity": "critical"}] if pe_likely else [{"text": "PE unlikely - a D-dimer can reasonably be used to guide the need for imaging", "severity": "caution"}],
            "notes": "Using the simplified two-tier interpretation (score of 4 or less = unlikely, more than 4 = likely) - some versions instead use a 3-tier low/moderate/high scheme with different cut points. Verify which version your institutional pathway uses.",
        }


class PERCRuleCalculator(Calculator):
    key = "perc_rule"

    def compute(self, a: dict) -> dict:
        fields = ["age50", "hr100", "o2sat95", "hemoptysis", "estrogen", "priorDvtPe", "legSwelling", "recentSurgery"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 8 criteria to apply the rule.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        any_positive = any(a.get(f) == "yes" for f in fields)
        return {
            "headline": "PERC criteria not met - PE cannot be ruled out by this rule alone." if any_positive else "All PERC criteria negative - in a patient already judged low pretest probability, PE can reasonably be ruled out without further testing.",
            "headlineSeverity": "caution" if any_positive else "good",
            "metrics": [{"label": "Criteria positive", "value": sum(1 for f in fields if a.get(f) == "yes"), "unit": "/ 8"}],
            "flags": [],
            "notes": "PERC is only valid in patients the clinician has already judged to be low pretest probability for PE - it should not be applied to patients with moderate or high pretest probability, and a single positive criterion means the rule does not apply.",
        }


class SPESICalculator(Calculator):
    key = "spesi"

    def compute(self, a: dict) -> dict:
        fields = ["age80", "cancer", "cardiopulmonary", "hr110", "sbp100", "o2sat90"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all 6 items to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        score = sum(1 for f in fields if a.get(f) == "yes")
        low_risk = score == 0
        return {
            "headline": "sPESI = 0 - low risk of 30-day mortality; may be a candidate for outpatient management." if low_risk else f"sPESI = {score} - higher risk; inpatient management generally favored.",
            "headlineSeverity": "good" if low_risk else ("critical" if score >= 2 else "warning"),
            "metrics": [{"label": "sPESI", "value": score, "unit": "/ 6"}],
            "flags": [{"text": "Any positive criterion generally favors inpatient management or closer monitoring", "severity": "critical" if score >= 2 else "warning"}] if not low_risk else [],
            "notes": "A score of 0 identifies patients at low risk for 30-day mortality - outpatient management still requires adequate social support, follow-up access, and absence of other reasons for admission (e.g. right heart strain, uncontrolled pain).",
        }
