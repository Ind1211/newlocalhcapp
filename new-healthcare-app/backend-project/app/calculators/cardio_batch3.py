from app.calculators.base import Calculator
from app.calculators.cardio_batch1 import _num_or_none


def _list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


class StatinBenefitGroupCalculator(Calculator):
    key = "statin_benefit_group"

    def compute(self, a: dict) -> dict:
        fields = ["clinicalAscvd", "ldl190", "age4075", "diabetes", "ldl70to189", "elevatedRisk"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to determine applicable statin benefit group(s).", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        groups = []
        if a.get("clinicalAscvd") == "yes":
            groups.append("Group 1: Clinical ASCVD - high-intensity statin generally indicated")
        if a.get("ldl190") == "yes":
            groups.append("Group 2: LDL 190 mg/dL or higher - high-intensity statin generally indicated")
        if a.get("age4075") == "yes" and a.get("diabetes") == "yes" and a.get("ldl70to189") == "yes":
            groups.append("Group 3: Diabetes, age 40-75, LDL 70-189 - moderate-intensity statin generally indicated")
        if a.get("age4075") == "yes" and a.get("diabetes") == "no" and a.get("ldl70to189") == "yes" and a.get("elevatedRisk") == "yes":
            groups.append("Group 4: Age 40-75, LDL 70-189, elevated estimated risk - statin therapy generally indicated")
        return {
            "headline": f"{len(groups)} statin benefit group(s) apply" if groups else "No statin benefit group criteria met from entries",
            "headlineSeverity": "caution" if groups else "good",
            "metrics": [],
            "flags": [{"text": g, "severity": "caution"} for g in groups],
            "notes": "Based on the commonly cited ACC/AHA statin benefit groups framework - individual statin choice and intensity should also account for side effects, drug interactions, and patient preference.",
        }


class HTNManagementChecklistCalculator(Calculator):
    key = "htn_management_checklist"

    def compute(self, a: dict) -> dict:
        fields = ["lifestyleCounseling", "homeMonitoring", "medicationStarted", "secondaryCausesConsidered", "followUpScheduled"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess completeness.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        met = sum(1 for f in fields if a.get(f) == "yes")
        missing = len(fields) - met
        pct = round((met / len(fields)) * 100)
        return {
            "headline": "All standard management steps addressed." if missing == 0 else f"{missing} management step(s) outstanding.",
            "headlineSeverity": "good" if missing == 0 else ("warning" if missing >= 3 else "caution"),
            "metrics": [{"label": "Completion", "value": pct, "unit": "%"}],
            "flags": [{"text": f"{missing} step(s) not yet addressed", "severity": "warning" if missing >= 3 else "caution"}] if missing > 0 else [],
            "notes": "Individual applicability varies (e.g. secondary-cause workup is not needed for every patient) - use clinical judgment on which items genuinely apply.",
        }


class DukeCriteriaCalculator(Calculator):
    key = "duke_criteria"

    def compute(self, a: dict) -> dict:
        fields = ["majorBloodCulture", "majorEcho", "minorPredisposition", "minorFever", "minorVascular", "minorImmunologic", "minorMicrobiologic"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to classify.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        major_count = sum(1 for f in ["majorBloodCulture", "majorEcho"] if a.get(f) == "yes")
        minor_count = sum(1 for f in ["minorPredisposition", "minorFever", "minorVascular", "minorImmunologic", "minorMicrobiologic"] if a.get(f) == "yes")
        if major_count >= 2 or (major_count >= 1 and minor_count >= 3) or minor_count >= 5:
            category = "Definite"
        elif (major_count >= 1 and minor_count >= 1) or minor_count >= 3:
            category = "Possible"
        else:
            category = "Rejected"
        sev_map = {"Definite": "critical", "Possible": "warning", "Rejected": "good"}
        flags = []
        if category == "Definite":
            flags.append({"text": "Definite endocarditis by Duke criteria - confirm infectious disease and cardiology involvement, and evaluate for surgical indications", "severity": "critical"})
        elif category == "Possible":
            flags.append({"text": "Possible endocarditis - further workup (repeat cultures, echocardiography, consider TEE) generally warranted", "severity": "warning"})
        return {
            "headline": f"{category} infective endocarditis by modified Duke criteria ({major_count} major, {minor_count} minor).",
            "headlineSeverity": sev_map[category],
            "metrics": [{"label": "Major criteria", "value": major_count, "unit": "/ 2"}, {"label": "Minor criteria", "value": minor_count, "unit": "/ 5"}],
            "flags": flags,
            "notes": "The modified Duke criteria are a clinical classification framework, not a definitive diagnostic test - \"Possible\" classification often still warrants treatment pending further evaluation, and clinical judgment can override a \"Rejected\" classification if suspicion remains high.",
        }


class EndocarditisProphylaxisCalculator(Calculator):
    key = "endocarditis_prophylaxis"

    def compute(self, a: dict) -> dict:
        fields = ["prostheticValve", "priorEndocarditis", "congenitalHighRisk", "transplantValvulopathy"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to determine prophylaxis indication.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        indicated = any(a.get(f) == "yes" for f in fields)
        return {
            "headline": "Antibiotic prophylaxis is indicated for qualifying dental and other high-risk procedures." if indicated else "No AHA-recognized high-risk condition identified - routine prophylaxis generally not indicated.",
            "headlineSeverity": "warning" if indicated else "good",
            "metrics": [],
            "flags": [{"text": "Prophylaxis is generally recommended only for specific procedures (e.g. dental procedures involving gingival manipulation), not for all medical or dental care", "severity": "warning"}] if indicated else [],
            "notes": "Based on the commonly cited AHA high-risk cardiac conditions list - the decision to give prophylaxis also depends on the specific procedure being performed, not the cardiac condition alone.",
        }


class TAAThresholdCalculator(Calculator):
    key = "taa_threshold"

    def compute(self, a: dict) -> dict:
        d = _num_or_none(a.get("diameter"))
        if d is None or not a.get("highRiskFeatures"):
            return {"headline": "Enter aortic diameter and risk-feature status to compare against thresholds.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        threshold = 4.5 if a.get("highRiskFeatures") == "yes" else 5.5
        approaching = threshold - 0.5 <= d < threshold
        met = d >= threshold
        if met:
            headline = f"Diameter {d:g} cm meets or exceeds the commonly cited {threshold:g} cm intervention threshold for this risk profile."
        elif approaching:
            headline = f"Diameter {d:g} cm is approaching the {threshold:g} cm threshold - close surveillance generally warranted."
        else:
            headline = f"Diameter {d:g} cm is below the {threshold:g} cm threshold for this risk profile."
        return {
            "headline": headline,
            "headlineSeverity": "critical" if met else ("warning" if approaching else "good"),
            "metrics": [{"label": "Diameter", "value": d, "unit": "cm"}, {"label": "Applicable threshold", "value": threshold, "unit": "cm"}],
            "flags": [{"text": "Consider surgical or endovascular referral - exact timing also depends on growth rate, symptoms, and surgical risk", "severity": "critical"}] if met else [],
            "notes": "Thresholds shown are commonly cited approximations (lower threshold for Marfan, connective tissue disease, bicuspid valve, or rapid growth) - verify against current society guidelines and individualize based on body size, growth rate, and surgical risk.",
        }


class CardiacRehabEligibilityCalculator(Calculator):
    key = "cardiac_rehab_eligibility"

    def compute(self, a: dict) -> dict:
        qualifiers = ["recentMi", "revascularization", "stableAngina", "hfref", "valveSurgery", "transplant"]
        if any(not a.get(f) for f in qualifiers) or not a.get("referred") or not a.get("enrolled"):
            return {"headline": "Answer all items to assess eligibility and referral status.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        eligible = any(a.get(f) == "yes" for f in qualifiers)
        if not eligible:
            return {"headline": "No standard qualifying diagnosis identified from entries.", "headlineSeverity": "good", "metrics": [], "flags": [], "notes": "Cardiac rehabilitation may still be considered case-by-case even without a standard qualifying diagnosis - discuss with the care team if benefit is anticipated."}
        flags = []
        if a.get("referred") == "no":
            flags.append({"text": "Eligible but not yet referred to cardiac rehabilitation", "severity": "warning"})
        elif a.get("enrolled") == "no":
            flags.append({"text": "Referred but not yet enrolled or attending - consider addressing barriers to enrollment", "severity": "caution"})
        return {
            "headline": flags[0]["text"] if flags else "Eligible and enrolled in cardiac rehabilitation.",
            "headlineSeverity": ("warning" if a.get("referred") == "no" else "caution") if flags else "good",
            "metrics": [],
            "flags": flags,
            "notes": "Cardiac rehabilitation is associated with reduced mortality and hospital readmission - referral and enrollment are both frequently underutilized relative to eligibility.",
        }


class AnginaPatientReportedCalculator(Calculator):
    key = "angina_patient_reported"

    def compute(self, a: dict) -> dict:
        if not a.get("anginaFrequency") or a.get("activityLimitation") in (None, "") or a.get("treatmentSatisfaction") in (None, ""):
            return {"headline": "Answer all items to summarize patient-reported impact.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        frequent_angina = a["anginaFrequency"] in ("Daily", "Multiple times a day")
        high_limitation = float(a["activityLimitation"]) >= 7
        low_satisfaction = float(a["treatmentSatisfaction"]) <= 3
        flags = []
        if frequent_angina or high_limitation:
            flags.append({"text": "Frequent angina or high activity limitation - consider reassessing anti-anginal therapy or referral for further ischemic workup", "severity": "warning"})
        if low_satisfaction:
            flags.append({"text": "Low treatment satisfaction reported - explore specific concerns and barriers to symptom control", "severity": "caution"})
        return {
            "headline": f"{len(flags)} area(s) of concern identified" if flags else "No major areas of concern from patient-reported responses",
            "headlineSeverity": ("warning" if (frequent_angina or high_limitation) else "caution") if flags else "good",
            "metrics": [
                {"label": "Angina frequency", "value": a["anginaFrequency"]},
                {"label": "Activity limitation", "value": a["activityLimitation"], "unit": "/10"},
                {"label": "Treatment satisfaction", "value": a["treatmentSatisfaction"], "unit": "/10"},
            ],
            "flags": flags,
            "notes": "An original tool covering common angina-specific quality-of-life domains - it is not a reproduction of the copyrighted Seattle Angina Questionnaire (SAQ), which would require separate licensing. If your institution has SAQ licensed, prefer it for standardized, validated scoring.",
        }


class CardiacRehabProgressCalculator(Calculator):
    key = "cardiac_rehab_progress"

    def compute(self, a: dict) -> dict:
        attended, prescribed = _num_or_none(a.get("sessionsAttended")), _num_or_none(a.get("sessionsPrescribed"))
        if not a.get("phase") or attended is None or prescribed is None or prescribed <= 0 or not a.get("functionalImprovement"):
            return {"headline": "Answer all items to summarize progress.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        pct = round((attended / prescribed) * 100)
        low_attendance = pct < 50
        flags = []
        if low_attendance:
            flags.append({"text": "Attendance below half of prescribed sessions - explore barriers (transportation, scheduling, symptoms, motivation)", "severity": "warning"})
        if a.get("functionalImprovement") == "no":
            flags.append({"text": "No reported functional improvement yet - reassess exercise prescription and rule out clinical barriers", "severity": "caution"})
        return {
            "headline": f"{len(flags)} area(s) of concern identified" if flags else "On track with cardiac rehabilitation progress",
            "headlineSeverity": "warning" if low_attendance else ("caution" if flags else "good"),
            "metrics": [{"label": "Attendance", "value": pct, "unit": "%"}, {"label": "Sessions", "value": f"{attended:g} of {prescribed:g}"}],
            "flags": flags,
            "notes": "Attendance and functional gains both matter - low attendance with reported improvement, or full attendance without improvement, each warrant a different follow-up conversation.",
        }


class CardiacRehabExerciseRiskCalculator(Calculator):
    key = "cardiac_rehab_exercise_risk"

    def compute(self, a: dict) -> dict:
        fields = ["reducedEf", "exerciseArrhythmia", "abnormalHemodynamics", "lowFunctionalCapacity", "anginaWithExertion", "survivedArrest"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to stratify exercise risk.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        high_risk_count = sum(1 for f in fields if a.get(f) == "yes")
        if a.get("survivedArrest") == "yes" or high_risk_count >= 2:
            risk = "High"
        elif high_risk_count == 1:
            risk = "Moderate"
        else:
            risk = "Low"
        sev_map = {"Low": "good", "Moderate": "caution", "High": "critical"}
        return {
            "headline": f"{risk} risk for exercise-related cardiac events.",
            "headlineSeverity": sev_map[risk],
            "metrics": [{"label": "Risk category", "value": risk}, {"label": "Risk factors present", "value": high_risk_count, "unit": "/ 6"}],
            "flags": [{"text": "High-risk classification generally warrants continuously supervised, ECG-monitored exercise sessions", "severity": "critical"}] if risk == "High" else [],
            "notes": "Based on commonly cited risk-stratification concepts (e.g. AACVPR categories) used to guide supervision level - exact criteria vary somewhat by source, and clinical judgment should override a borderline classification.",
        }


class WideComplexTachycardiaCalculator(Calculator):
    key = "wide_complex_tachycardia"

    def compute(self, a: dict) -> dict:
        fields = ["avDissociation", "fusionCaptureBeats", "extremeAxis", "precordialConcordance", "wideQrs", "structuralHeartDisease"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        strongly_favors_vt = a.get("avDissociation") == "yes" or a.get("fusionCaptureBeats") == "yes"
        if strongly_favors_vt or count >= 2:
            headline = f"{count} feature(s) favoring VT - treat as ventricular tachycardia until proven otherwise."
        else:
            headline = f"{count} feature(s) favoring VT - findings less specific, but VT remains the safer default assumption in hemodynamically unstable or ambiguous cases."
        return {
            "headline": headline,
            "headlineSeverity": "critical" if strongly_favors_vt else ("warning" if count >= 1 else "caution"),
            "metrics": [{"label": "Features favoring VT", "value": count, "unit": "/ 6"}],
            "flags": [{"text": "AV dissociation or fusion/capture beats are highly specific for VT", "severity": "critical"}] if strongly_favors_vt else [],
            "notes": "In a hemodynamically unstable patient, do not delay treatment to complete this checklist - when uncertain, wide complex tachycardia should generally be treated as VT rather than assumed to be SVT with aberrancy.",
        }


class AAAThresholdCalculator(Calculator):
    key = "aaa_threshold"

    def compute(self, a: dict) -> dict:
        d = _num_or_none(a.get("diameter"))
        if not a.get("sex") or not a.get("everSmoked") or not a.get("age6575"):
            return {"headline": "Answer all items to assess screening and threshold status.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        screening_indicated = a.get("sex") == "male" and a.get("everSmoked") == "yes" and a.get("age6575") == "yes"
        if d is None:
            return {
                "headline": "One-time screening ultrasound is generally recommended for this profile." if screening_indicated else "Routine AAA screening is not generally recommended for this profile - enter a known diameter if already measured.",
                "headlineSeverity": "warning" if screening_indicated else "good",
                "metrics": [],
                "flags": [{"text": "One-time ultrasound screening is commonly recommended for men aged 65-75 who have ever smoked", "severity": "warning"}] if screening_indicated else [],
                "notes": "Based on commonly cited USPSTF-style screening criteria - individual guidelines vary, and screening in other groups (e.g. women with a smoking history or family history) may still be reasonable case-by-case.",
            }
        threshold = 5.0 if a.get("sex") == "female" else 5.5
        met = d >= threshold
        approaching = threshold - 0.5 <= d < threshold
        if met:
            headline = f"Diameter {d:g} cm meets or exceeds the commonly cited {threshold:g} cm repair threshold."
        elif approaching:
            headline = f"Diameter {d:g} cm is approaching the {threshold:g} cm threshold - closer surveillance intervals generally warranted."
        else:
            headline = f"Diameter {d:g} cm is below the {threshold:g} cm threshold."
        return {
            "headline": headline,
            "headlineSeverity": "critical" if met else ("warning" if approaching else "good"),
            "metrics": [{"label": "Diameter", "value": d, "unit": "cm"}, {"label": "Applicable threshold", "value": threshold, "unit": "cm"}],
            "flags": [{"text": "Consider vascular surgery referral for repair evaluation - rapid growth or symptoms can lower the threshold for intervention", "severity": "critical"}] if met else [],
            "notes": "Thresholds shown are commonly cited approximations (5.5 cm men, 5.0 cm women) - verify against current society guidelines, and surveillance intervals should scale with current size.",
        }


class PostpartumCVRiskCalculator(Calculator):
    key = "postpartum_cv_risk"

    def compute(self, a: dict) -> dict:
        fields = ["preeclampsia", "gestationalHtn", "gestationalDiabetes", "pretermDelivery", "smallForGestAge"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to screen.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        return {
            "headline": f"{count} pregnancy-associated cardiovascular risk factor(s) identified." if count > 0 else "No pregnancy-associated cardiovascular risk factors identified from entries.",
            "headlineSeverity": "warning" if count >= 2 else ("caution" if count == 1 else "good"),
            "metrics": [{"label": "Risk factors present", "value": count, "unit": "/ 5"}],
            "flags": [{"text": "Adverse pregnancy outcomes are established cardiovascular risk-enhancing factors - consider earlier and more frequent cardiovascular risk assessment going forward", "severity": "warning" if count >= 2 else "caution"}] if count > 0 else [],
            "notes": "These findings should be factored into long-term cardiovascular risk assessment (alongside standard risk factors), not treated as a one-time postpartum concern only.",
        }
