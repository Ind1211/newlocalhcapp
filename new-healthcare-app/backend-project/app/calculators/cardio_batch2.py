from app.calculators.base import Calculator


def _list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


class PostMICalculator(Calculator):
    key = "post_mi_checklist"

    def compute(self, a: dict) -> dict:
        fields = ["aspirin", "p2y12", "statin", "betaBlocker", "acei", "cardiacRehab", "smoking", "bpControl"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess completeness.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        met = sum(1 for f in fields if a.get(f) == "yes")
        missing = len(fields) - met
        pct = round((met / len(fields)) * 100)
        return {
            "headline": "All secondary prevention measures addressed." if missing == 0 else f"{missing} secondary prevention measure(s) outstanding.",
            "headlineSeverity": "good" if missing == 0 else ("warning" if missing >= 3 else "caution"),
            "metrics": [{"label": "Completion", "value": pct, "unit": "%"}],
            "flags": [{"text": f"{missing} measure(s) not yet addressed - review before discharge or at next follow-up", "severity": "warning" if missing >= 3 else "caution"}] if missing > 0 else [],
            "notes": "A checklist of commonly cited guideline-directed secondary prevention measures - individual applicability varies (e.g. ACEi/ARB indication depends on EF, hypertension, or diabetes status), so absence of a measure is not automatically a gap in care.",
        }


class DeviceFollowupCalculator(Calculator):
    key = "device_followup"

    def compute(self, a: dict) -> dict:
        fields = ["battery", "leads", "shocks", "symptoms", "siteCheck"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to complete the follow-up check.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        concerns = []
        if a.get("battery") == "no":
            concerns.append("Battery status outside expected range")
        if a.get("leads") == "no":
            concerns.append("Lead parameters not stable")
        if a.get("shocks") == "yes":
            concerns.append("Shock(s) since last visit - requires interrogation and cause review")
        if a.get("symptoms") == "yes":
            concerns.append("Symptoms suggesting possible device malfunction")
        if a.get("siteCheck") == "no":
            concerns.append("Device pocket site abnormality noted")
        return {
            "headline": "Device follow-up unremarkable." if not concerns else f"{len(concerns)} finding(s) requiring follow-up.",
            "headlineSeverity": "good" if not concerns else ("critical" if len(concerns) >= 2 else "warning"),
            "metrics": [],
            "flags": [{"text": c, "severity": "warning"} for c in concerns],
            "notes": "A routine follow-up checklist - device interrogation findings should be reviewed by electrophysiology or the device manufacturer representative per institution protocol.",
        }


class ACHDSymptomScreenCalculator(Calculator):
    key = "achd_symptom_screen"

    def compute(self, a: dict) -> dict:
        fields = ["cyanosis", "exercise", "arrhythmiaSymptoms", "heartFailureSymptoms", "hemoptysis"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to complete the screen.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        positives = [f for f in fields if a.get(f) == "yes"]
        return {
            "headline": "No warning symptoms reported." if not positives else f"{len(positives)} warning symptom(s) reported.",
            "headlineSeverity": "good" if not positives else ("critical" if len(positives) >= 2 else "warning"),
            "metrics": [],
            "flags": [{"text": "Any new symptom in an ACHD patient warrants prompt evaluation, ideally in consultation with an ACHD specialist", "severity": "critical" if len(positives) >= 2 else "warning"}] if positives else [],
            "notes": "Adults with congenital heart disease can decompensate subtly - a low threshold for further evaluation is generally appropriate even with a single new symptom.",
        }


class PPCMScreenCalculator(Calculator):
    key = "ppcm_screen"

    def compute(self, a: dict) -> dict:
        fields = ["timing", "noPriorHeartDisease", "hfSymptoms", "reducedEf"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to screen.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        met = sum(1 for f in fields if a.get(f) == "yes")
        suggestive = all(a.get(f) == "yes" for f in fields)
        return {
            "headline": "Findings are consistent with peripartum cardiomyopathy - confirm with echocardiography and cardiology evaluation." if suggestive else "Findings are not fully consistent with the typical peripartum cardiomyopathy presentation.",
            "headlineSeverity": "critical" if suggestive else ("warning" if met >= 2 else "good"),
            "metrics": [{"label": "Criteria met", "value": met, "unit": "/ 4"}],
            "flags": [{"text": "Urgent cardiology evaluation warranted - peripartum cardiomyopathy carries real maternal risk and needs prompt heart-failure-directed management", "severity": "critical"}] if suggestive else [],
            "notes": "Peripartum cardiomyopathy is a diagnosis of exclusion requiring echocardiographic confirmation of reduced EF without another identifiable cause - this is a screening aid, not a substitute for that workup.",
        }


class ASCVDRiskEnhancersCalculator(Calculator):
    key = "ascvd_risk_enhancers"

    def compute(self, a: dict) -> dict:
        flags = []
        if a.get("familyHistory") == "yes":
            flags.append({"text": "Family history of premature ASCVD - established risk-enhancing factor.", "severity": "caution"})
        if a.get("ckd") == "yes":
            flags.append({"text": "Chronic kidney disease - established risk-enhancing factor.", "severity": "caution"})
        if a.get("metabolicSyndrome") == "yes":
            flags.append({"text": "Metabolic syndrome - established risk-enhancing factor.", "severity": "caution"})
        if a.get("inflammatory") == "yes":
            flags.append({"text": "Chronic inflammatory condition - established risk-enhancing factor.", "severity": "caution"})
        if a.get("ethnicity") == "yes":
            flags.append({"text": "South Asian ancestry - recognized risk-enhancing factor in ACC/AHA guidance.", "severity": "caution"})
        if a.get("lipidMarkers") == "yes":
            flags.append({"text": "Elevated LDL or Lp(a) - additional risk-enhancing factor and potentially modifiable.", "severity": "warning"})
        if a.get("womensHistory") == "yes":
            flags.append({"text": "Premature menopause or adverse pregnancy history - established risk-enhancing factor specific to women.", "severity": "caution"})
        if a.get("triglycerides") == "yes":
            flags.append({"text": "Persistently elevated triglycerides - additional risk-enhancing factor and potentially modifiable.", "severity": "warning"})
        sev = "warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good")
        return {
            "headline": f"{len(flags)} ASCVD risk-enhancing factor(s) identified" if flags else "No risk-enhancing factors flagged from entries",
            "headlineSeverity": sev,
            "metrics": [],
            "flags": flags,
            "notes": "This tool intentionally does not compute a numeric 10-year ASCVD percentage - the ACC/AHA Pooled Cohort Equations require precise, race- and sex-specific coefficients best sourced from a validated calculator rather than reproduced here. Use your institution's validated ASCVD calculator for a numeric estimate, and weigh these factors most heavily when the calculated risk falls in a borderline or intermediate range.",
        }


class GRACERiskEnhancersCalculator(Calculator):
    key = "grace_risk_enhancers"

    def compute(self, a: dict) -> dict:
        flags = []
        if a.get("age75") == "yes":
            flags.append({"text": "Age 75 or older - one of the most heavily-weighted GRACE variables.", "severity": "warning"})
        if a.get("tachycardia") == "yes":
            flags.append({"text": "Tachycardia at presentation - GRACE risk factor.", "severity": "caution"})
        if a.get("hypotension") == "yes":
            flags.append({"text": "Hypotension at presentation - GRACE risk factor and hemodynamically significant.", "severity": "warning"})
        if a.get("renalImpairment") == "yes":
            flags.append({"text": "Renal impairment - GRACE risk factor; also relevant to drug dosing and contrast use.", "severity": "warning"})
        if a.get("killipElevated") == "yes":
            flags.append({"text": "Killip class II or higher - GRACE risk factor reflecting heart failure at presentation.", "severity": "warning"})
        if a.get("cardiacArrest") == "yes":
            flags.append({"text": "Cardiac arrest at admission - one of the most heavily-weighted GRACE variables.", "severity": "critical"})
        if a.get("stDeviation") == "yes":
            flags.append({"text": "ST-segment deviation - GRACE risk factor.", "severity": "caution"})
        if a.get("elevatedMarkers") == "yes":
            flags.append({"text": "Elevated cardiac biomarkers - GRACE risk factor.", "severity": "caution"})
        sev = "critical" if any(f["severity"] == "critical" for f in flags) else ("warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good"))
        return {
            "headline": f"{len(flags)} GRACE-relevant high-risk feature(s) identified" if flags else "No GRACE-relevant high-risk features flagged from entries",
            "headlineSeverity": sev,
            "metrics": [],
            "flags": flags,
            "notes": "This tool intentionally does not compute a numeric GRACE score or mortality percentage - GRACE uses a nomogram-derived, non-linear point system across continuous variables best sourced from a validated calculator (available through your EHR or standard clinical references) rather than reproduced here. Cardiac arrest at admission and advanced age are typically the most heavily-weighted individual factors. Renal impairment is also a GRACE variable - a direct point of overlap with kidney function worth weighing alongside any concurrent kidney assessment.",
        }


class HFPatientReportedCalculator(Calculator):
    key = "hf_patient_reported"

    def compute(self, a: dict) -> dict:
        scales = ["physicalLimitation", "qualityOfLife", "socialLimitation", "selfEfficacy"]
        if any(a.get(f) is None or a.get(f) == "" for f in scales) or not a.get("symptomFrequency"):
            return {"headline": "Answer all items to summarize patient-reported impact.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        high_burden = float(a["physicalLimitation"]) >= 7 or float(a["qualityOfLife"]) >= 7 or float(a["socialLimitation"]) >= 7 or a["symptomFrequency"] in ("Daily", "Constantly")
        low_confidence = float(a["selfEfficacy"]) <= 3
        flags = []
        if high_burden:
            flags.append({"text": "High patient-reported symptom or functional burden - consider reassessing heart failure therapy optimization", "severity": "warning"})
        if low_confidence:
            flags.append({"text": "Low self-reported confidence in symptom self-management - consider additional patient education or a heart failure clinic referral", "severity": "caution"})
        return {
            "headline": f"{len(flags)} area(s) of concern identified" if flags else "No major areas of concern from patient-reported responses",
            "headlineSeverity": ("warning" if high_burden else "caution") if flags else "good",
            "metrics": [
                {"label": "Physical limitation", "value": a["physicalLimitation"], "unit": "/10"},
                {"label": "Symptom frequency", "value": a["symptomFrequency"]},
                {"label": "Quality of life impact", "value": a["qualityOfLife"], "unit": "/10"},
                {"label": "Social limitation", "value": a["socialLimitation"], "unit": "/10"},
                {"label": "Self-management confidence", "value": a["selfEfficacy"], "unit": "/10"},
            ],
            "flags": flags,
            "notes": "This is an original tool covering common heart-failure-specific quality-of-life domains (physical limitation, symptom burden, social impact, self-efficacy). It is not a reproduction of the copyrighted Kansas City Cardiomyopathy Questionnaire (KCCQ), which would require separate licensing - if your institution has KCCQ licensed, prefer it for standardized, validated scoring.",
        }


class AdvancedHFGoalsOfCareCalculator(Calculator):
    key = "advanced_hf_goals_of_care"

    LABELS = {
        "prognosisDiscussed": "Prognosis discussion", "goalsOfCareDiscussed": "Goals-of-care discussion",
        "advanceDirectiveDocumented": "Advance directive or proxy", "palliativeCareReferral": "Palliative care referral",
        "icdDiscussed": "ICD deactivation discussion", "hospiceEligibility": "Hospice eligibility consideration",
    }

    def compute(self, a: dict) -> dict:
        outstanding = [k for k in self.LABELS if a.get(k) != "yes"]
        flags = [{"text": f"{self.LABELS[k]} not yet confirmed.", "severity": "caution"} for k in outstanding]
        return {
            "headline": "All standard goals-of-care items addressed" if not outstanding else f"{len(outstanding)} item(s) outstanding",
            "headlineSeverity": "good" if not outstanding else ("warning" if len(outstanding) >= 3 else "caution"),
            "metrics": [],
            "flags": flags,
            "notes": "A checklist to support, not replace, an individualized goals-of-care conversation - not every item applies to every patient (e.g. ICD deactivation only if a device is present).",
        }


class ICDDeactivationChecklistCalculator(Calculator):
    key = "icd_deactivation_checklist"

    LABELS = {
        "shockVsPacingExplained": "Shock vs. pacing explanation", "patientPreferenceElicited": "Patient or surrogate preference",
        "familyIncluded": "Family or surrogate inclusion", "documented": "Documentation", "epTeamContacted": "EP or device team contact",
    }

    def compute(self, a: dict) -> dict:
        outstanding = [k for k in self.LABELS if a.get(k) != "yes"]
        flags = [{"text": f"{self.LABELS[k]} not yet confirmed.", "severity": "caution"} for k in outstanding]
        return {
            "headline": "All standard ICD deactivation discussion items addressed" if not outstanding else f"{len(outstanding)} item(s) outstanding",
            "headlineSeverity": "good" if not outstanding else ("warning" if len(outstanding) >= 2 else "caution"),
            "metrics": [],
            "flags": flags,
            "notes": "Deactivating shock therapy is generally considered ethically and legally equivalent to withholding other life-sustaining treatment - pacing function is usually continued separately for comfort unless otherwise indicated. Involve palliative care and the device team as needed.",
        }


class VasovagalFeaturesCalculator(Calculator):
    key = "vasovagal_features"

    def compute(self, a: dict) -> dict:
        fields = ["prolongedStanding", "triggerEmotion", "situational", "prodrome", "rapidRecovery"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        return {
            "headline": f"{count} classic feature(s) present - supportive of vasovagal syncope." if count >= 2 else f"{count} classic feature(s) present - less typical for vasovagal syncope.",
            "headlineSeverity": "good" if count >= 2 else "caution",
            "metrics": [{"label": "Features present", "value": count, "unit": "/ 5"}],
            "flags": [{"text": "Few classic vasovagal features - consider a broader syncope workup (cardiac, orthostatic, neurologic causes)", "severity": "caution"}] if count < 2 else [],
            "notes": "Classic vasovagal features support but do not confirm the diagnosis. Red-flag features (exertional onset, no prodrome, family history of sudden death, abnormal ECG) should prompt cardiac evaluation regardless of these findings.",
        }


class TamponadeScreenCalculator(Calculator):
    key = "tamponade_screen"

    def compute(self, a: dict) -> dict:
        fields = ["hypotension", "jvd", "muffledHeartSounds", "pulsusParadoxus", "tachycardia"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to screen.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        beck_count = sum(1 for f in ["hypotension", "jvd", "muffledHeartSounds"] if a.get(f) == "yes")
        total_count = sum(1 for f in fields if a.get(f) == "yes")
        full_triad = beck_count == 3
        if full_triad:
            headline, sev = "Full Beck triad present - high suspicion for cardiac tamponade, this is an emergency.", "critical"
        elif total_count >= 2:
            headline, sev = f"{total_count} of 5 findings present - tamponade should be considered.", "warning"
        else:
            headline, sev = f"{total_count} of 5 findings present - tamponade less likely but cannot be excluded clinically.", "good"
        return {
            "headline": headline,
            "headlineSeverity": sev,
            "metrics": [{"label": "Beck triad components", "value": beck_count, "unit": "/ 3"}, {"label": "Total findings", "value": total_count, "unit": "/ 5"}],
            "flags": [{"text": "The full Beck triad is a late and insensitive finding - do not wait for all three before pursuing urgent echocardiography if tamponade is suspected", "severity": "critical"}] if full_triad else [],
            "notes": "The Beck triad is classic but insensitive - many patients with tamponade do not display all three findings. Echocardiography is the standard way to confirm the diagnosis; do not delay imaging or intervention while awaiting the full clinical triad.",
        }


class PericarditisAdmissionRiskCalculator(Calculator):
    key = "pericarditis_admission_risk"

    def compute(self, a: dict) -> dict:
        fields = ["fever", "subacuteOnset", "largeEffusion", "immunosuppressed", "anticoagulated", "traumaticOrigin", "noNsaidResponse"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess admission risk factors.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        return {
            "headline": f"{count} high-risk feature(s) present - hospital admission generally favored." if count > 0 else "No high-risk features present - outpatient management may be reasonable.",
            "headlineSeverity": "critical" if count >= 2 else ("warning" if count == 1 else "good"),
            "metrics": [{"label": "High-risk features", "value": count, "unit": "/ 7"}],
            "flags": [{"text": "Presence of any major risk factor generally favors admission for further workup and monitoring", "severity": "critical" if count >= 2 else "warning"}] if count > 0 else [],
            "notes": "Commonly cited features favoring admission in acute pericarditis - clinical judgment and the specific combination of factors matter more than a simple count.",
        }


class HCMSCDRiskEnhancersCalculator(Calculator):
    key = "hcm_scd_risk_enhancers"

    def compute(self, a: dict) -> dict:
        fields = ["familyHistorySCD", "unexplainedSyncope", "nsvt", "massiveHypertrophy", "abnormalBpResponse", "lvotObstruction"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        count = sum(1 for f in fields if a.get(f) == "yes")
        major_present = any(a.get(f) == "yes" for f in ["familyHistorySCD", "unexplainedSyncope", "nsvt", "massiveHypertrophy"])
        return {
            "headline": f"{count} recognized SCD risk factor(s) identified" if count > 0 else "No major SCD risk factors flagged from entries",
            "headlineSeverity": "critical" if major_present else ("warning" if count > 0 else "good"),
            "metrics": [],
            "flags": [{"text": "Discuss ICD candidacy with electrophysiology using a validated HCM-SCD risk calculator alongside these factors", "severity": "critical" if major_present else "warning"}] if count > 0 else [],
            "notes": "This tool intentionally does not compute a numeric 5-year sudden death risk percentage - the HCM Risk-SCD model uses precise coefficients best sourced from a validated calculator rather than reproduced here. Use a validated HCM-SCD risk calculator for a numeric estimate alongside these established risk factors.",
        }


class TakotsuboCriteriaCalculator(Calculator):
    key = "takotsubo_criteria"

    def compute(self, a: dict) -> dict:
        fields = ["wallMotion", "noObstructiveCad", "newEcgOrTroponin", "noPheoMyocarditis", "stressTrigger"]
        if any(not a.get(f) for f in fields):
            return {"headline": "Answer all items to assess.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        core_criteria = a.get("wallMotion") == "yes" and a.get("noObstructiveCad") == "yes" and a.get("noPheoMyocarditis") == "yes"
        count = sum(1 for f in fields if a.get(f) == "yes")
        return {
            "headline": "Core diagnostic criteria satisfied - consistent with takotsubo cardiomyopathy." if core_criteria else f"{count} of 5 features present - core diagnostic criteria not fully satisfied.",
            "headlineSeverity": "warning" if core_criteria else "caution",
            "metrics": [{"label": "Features present", "value": count, "unit": "/ 5"}],
            "flags": [{"text": "Takotsubo cardiomyopathy can still carry serious complications (heart failure, arrhythmia, LV outflow obstruction) despite being reversible - manage as clinically indicated, not as benign by default", "severity": "warning"}] if core_criteria else [],
            "notes": "Based on commonly cited diagnostic frameworks (InterTAK/Mayo criteria concepts). Obstructive CAD and takotsubo can coexist, so coronary assessment is still generally warranted rather than assumed mutually exclusive.",
        }
