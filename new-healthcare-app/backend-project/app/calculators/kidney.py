import math
from app.calculators.base import Calculator


def _list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


def _num_or_none(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


class KFRECalculator(Calculator):
    key = "kfre"

    def compute(self, a: dict) -> dict:
        age = _num_or_none(a.get("age"))
        egfr = _num_or_none(a.get("egfr"))
        acr = _num_or_none(a.get("acr"))
        sex = a.get("sex")
        male = 1 if sex == "male" else (0 if sex == "female" else None)
        if age is None or egfr is None or acr is None or male is None or acr <= 0:
            return {"headline": "Enter age, sex, eGFR, and ACR to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        L = -0.2201 * (age / 10 - 7.036) + 0.2467 * (male - 0.5642) - 0.5567 * (egfr / 5 - 7.222) + 0.4510 * (math.log(acr) - 5.137)
        risk2 = 1 - 0.9750 ** math.exp(L)
        risk5 = 1 - 0.9240 ** math.exp(L)
        pct2, pct5 = round(risk2 * 100, 1), round(risk5 * 100, 1)
        flags = []
        sev = "good"
        if risk5 * 100 >= 5:
            flags.append({"text": "5-year risk \u22655% - commonly used threshold (NICE CKD guidance) for referral to nephrology.", "severity": "warning"})
            sev = "warning"
        if risk5 * 100 >= 15:
            flags.append({"text": "5-year risk \u226515% - high enough that some centers begin RRT-planning conversations.", "severity": "critical"})
            sev = "critical"
        return {
            "headline": f"2-year risk {pct2}% \u00b7 5-year risk {pct5}%",
            "headlineSeverity": sev,
            "metrics": [{"label": "2-year risk", "value": pct2, "unit": "%"}, {"label": "5-year risk", "value": pct5, "unit": "%"}],
            "flags": flags,
            "notes": "Validated in adults with eGFR <60 (CKD G3-G5), North American calibration. Not validated under age 18 or for eGFR \u226560 - treat results outside that range cautiously.",
        }


class AKIStagingCalculator(Calculator):
    key = "aki_staging"

    def compute(self, a: dict) -> dict:
        stage_from_scr = 0
        if a.get("onRRT") == "yes":
            stage_from_scr = 3
        else:
            base = _num_or_none(a.get("baselineScr"))
            cur = _num_or_none(a.get("currentScr"))
            if base is not None and cur is not None and base > 0:
                ratio = cur / base
                if ratio >= 3.0 or cur >= 4.0:
                    stage_from_scr = 3
                elif ratio >= 2.0:
                    stage_from_scr = 2
                elif ratio >= 1.5:
                    stage_from_scr = 1
            if a.get("scrRoseIn48h") == "yes":
                stage_from_scr = max(stage_from_scr, 1)

        stage_from_uo = 0
        uo = _num_or_none(a.get("urineOutput"))
        dur = _num_or_none(a.get("urineDurationHrs"))
        if a.get("haveUrineData") == "yes" and uo is not None and dur is not None:
            if uo == 0 and dur >= 12:
                stage_from_uo = 3
            elif uo < 0.3 and dur >= 24:
                stage_from_uo = 3
            elif uo < 0.5 and dur >= 12:
                stage_from_uo = 2
            elif uo < 0.5 and dur >= 6:
                stage_from_uo = 1

        final_stage = max(stage_from_scr, stage_from_uo)
        if final_stage == 0:
            return {
                "headline": "No KDIGO AKI stage met by the values entered.",
                "headlineSeverity": "good",
                "metrics": [{"label": "Creatinine-based stage", "value": stage_from_scr}, {"label": "Urine-output-based stage", "value": stage_from_uo}],
                "flags": [],
                "notes": "If clinical suspicion remains high, recheck creatinine trend and confirm urine output data are complete.",
            }
        flags = []
        if final_stage >= 1:
            flags.append({"text": "Review medication list for nephrotoxins and renally-cleared drugs needing dose adjustment.", "severity": "caution"})
        if final_stage >= 2:
            flags.append({"text": "Consider nephrology involvement.", "severity": "warning"})
        if final_stage == 3:
            flags.append({"text": "Meets KDIGO Stage 3 - evaluate need for renal replacement therapy and avoid further nephrotoxic exposure.", "severity": "critical"})
        return {
            "headline": f"KDIGO AKI Stage {final_stage}",
            "headlineSeverity": "critical" if final_stage == 3 else ("warning" if final_stage == 2 else "caution"),
            "metrics": [{"label": "Creatinine-based stage", "value": stage_from_scr}, {"label": "Urine-output-based stage", "value": stage_from_uo}, {"label": "Overall stage", "value": final_stage}],
            "flags": flags,
            "notes": "Based on the KDIGO 2012 AKI definition (creatinine fold-rise/absolute rise within 48h-7 days, or urine output criteria). Older RIFLE/AKIN systems use similar but not identical thresholds - KDIGO is the current harmonized standard.",
        }


class HDAdequacyCalculator(Calculator):
    key = "hd_adequacy"

    def compute(self, a: dict) -> dict:
        pre_bun = _num_or_none(a.get("preBUN"))
        post_bun = _num_or_none(a.get("postBUN"))
        t = _num_or_none(a.get("sessionHours"))
        uf = _num_or_none(a.get("ufVolume"))
        w = _num_or_none(a.get("postWeight"))
        if any(v is None for v in [pre_bun, post_bun, t, uf, w]) or pre_bun <= 0 or w <= 0:
            return {"headline": "Enter all five values to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        R = post_bun / pre_bun
        ktv = -math.log(R - 0.008 * t) + (4 - 3.5 * R) * (uf / w)
        urr = (1 - R) * 100
        flags = []
        sev = "good"
        if ktv < 1.2:
            flags.append({"text": "Below the KDOQI single-pool Kt/V target of 1.2 per session - consider increasing time, blood/dialysate flow, or dialyzer surface area.", "severity": "warning"})
            sev = "warning"
        if urr < 65:
            flags.append({"text": "URR below the commonly used 65% adequacy threshold.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"Kt/V {ktv:.2f} \u00b7 URR {urr:.0f}%",
            "headlineSeverity": sev,
            "metrics": [{"label": "Kt/V (Daugirdas)", "value": round(ktv, 2)}, {"label": "URR", "value": round(urr), "unit": "%"}],
            "flags": flags,
            "notes": "Daugirdas second-generation variable-volume single-pool Kt/V formula. Confirm pre/post BUN are from the same session and in matching units.",
        }


class PDAdequacyCalculator(Calculator):
    key = "pd_adequacy"

    def compute(self, a: dict) -> dict:
        age = _num_or_none(a.get("age"))
        h = _num_or_none(a.get("heightCm"))
        w = _num_or_none(a.get("weightKg"))
        pc = _num_or_none(a.get("peritonealUreaClearance"))
        rc = _num_or_none(a.get("residualRenalUreaClearance")) or 0
        sex = a.get("sex")
        if age is None or h is None or w is None or pc is None or not sex:
            return {"headline": "Enter age, sex, height, weight, and peritoneal urea clearance to calculate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        V = (2.447 - 0.09156 * age + 0.1074 * h + 0.3362 * w) if sex == "male" else (-2.097 + 0.1069 * h + 0.2466 * w)
        weekly_ktv = (pc + rc) / V
        flags = []
        sev = "good"
        if weekly_ktv < 1.7:
            flags.append({"text": "Below the KDOQI/ISPD weekly Kt/V target of 1.7 - review prescription (exchange volume/number, dwell time) and residual renal function.", "severity": "warning"})
            sev = "warning"
        metrics = [{"label": "Estimated V (Watson)", "value": round(V, 1), "unit": "L"}, {"label": "Weekly Kt/V", "value": round(weekly_ktv, 2)}]
        if a.get("havePet") == "yes" and a.get("petDpCr"):
            dpcr = _num_or_none(a.get("petDpCr"))
            if dpcr is not None:
                if dpcr > 0.81:
                    cat = "High transporter"
                elif dpcr >= 0.65:
                    cat = "High-average transporter"
                elif dpcr >= 0.50:
                    cat = "Low-average transporter"
                else:
                    cat = "Low transporter"
                metrics.append({"label": "PET category", "value": cat})
                if cat == "High transporter":
                    flags.append({"text": "Fast transporters often do better with shorter, more frequent exchanges (e.g. APD) - consider prescription review.", "severity": "caution"})
                if cat == "Low transporter":
                    flags.append({"text": "Slow transporters may need longer dwell times to achieve adequate solute clearance.", "severity": "caution"})
        return {
            "headline": f"Weekly Kt/V {weekly_ktv:.2f}",
            "headlineSeverity": sev,
            "metrics": metrics,
            "flags": flags,
            "notes": "Body water (V) estimated via the Watson formula; weekly Kt/V = (peritoneal + residual renal urea clearance) / V. Your PD unit's directly measured 24-hour collection remains the definitive value if available. PET categories per standard Twardowski thresholds.",
        }


class ADPKDMayoCalculator(Calculator):
    key = "adpkd_mayo"

    def compute(self, a: dict) -> dict:
        h = _num_or_none(a.get("heightCm"))
        tkv = _num_or_none(a.get("totalKidneyVolumeML"))
        if h is None or tkv is None or h <= 0:
            return {"headline": "Enter height and total kidney volume.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        httkv = tkv / (h / 100)
        flags = []
        sev = "good"
        if httkv >= 600:
            flags.append({"text": "htTKV \u2265600 mL/m - classic Mayo/CRISP threshold associated with high risk of progression to kidney failure within roughly a decade.", "severity": "warning"})
            sev = "warning"
        return {
            "headline": f"htTKV {httkv:.0f} mL/m",
            "headlineSeverity": sev,
            "metrics": [{"label": "htTKV", "value": round(httkv), "unit": "mL/m"}],
            "flags": flags,
            "notes": "Uses the single well-established htTKV \u2265600 mL/m risk threshold (Chapman/CRISP), not the full five-class (1A-1E) Mayo Imaging Classification, which also incorporates age-specific annual growth-rate percentiles. Use the Mayo calculator or formal imaging report for precise sub-classification.",
        }


class APOL1Calculator(Calculator):
    key = "apol1"

    def compute(self, a: dict) -> dict:
        if not a.get("allele1") or not a.get("allele2"):
            return {"headline": "Select both alleles.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        risk_count = (1 if a["allele1"] != "G0" else 0) + (1 if a["allele2"] != "G0" else 0)
        high_risk = risk_count == 2
        flags = []
        if high_risk:
            flags.append({"text": "Two APOL1 risk alleles - associated with increased risk of CKD progression, and relevant for counseling biologically related living-kidney-donor candidates.", "severity": "warning"})
        return {
            "headline": "High-risk genotype (2 risk alleles)" if high_risk else "Low-risk genotype",
            "headlineSeverity": "warning" if high_risk else "good",
            "metrics": [{"label": "Risk alleles", "value": risk_count}],
            "flags": flags,
            "notes": "Genetic counseling should accompany APOL1 testing and result disclosure, especially for related living-donor evaluation. This module only records genotype and the well-established two-risk-allele association.",
        }


class SchwartzCalculator(Calculator):
    key = "schwartz"

    def compute(self, a: dict) -> dict:
        h = _num_or_none(a.get("heightCm"))
        scr = _num_or_none(a.get("scr"))
        if h is None or scr is None or scr <= 0:
            return {"headline": "Enter height and creatinine.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        egfr = 0.413 * h / scr
        flags = []
        sev = "good"
        if egfr < 90:
            sev = "warning" if egfr < 60 else "caution"
            flags.append({"text": "Reduced eGFR for a pediatric patient - pediatric CKD staging and growth considerations differ from adults; involve pediatric nephrology.", "severity": sev})
        return {
            "headline": f"eGFR {egfr:.0f} mL/min/1.73m\u00b2",
            "headlineSeverity": sev,
            "metrics": [{"label": "eGFR", "value": round(egfr), "unit": "mL/min/1.73m\u00b2"}],
            "flags": flags,
            "notes": "Bedside Schwartz equation (2009, CKiD cohort) - intended for children/adolescents with stable kidney function; not validated for adults or for acutely unwell children with rapidly changing creatinine.",
        }


class MetabolicAcidosisCalculator(Calculator):
    key = "metabolic_acidosis"

    def compute(self, a: dict) -> dict:
        na = _num_or_none(a.get("sodium"))
        cl = _num_or_none(a.get("chloride"))
        hco3 = _num_or_none(a.get("bicarbonate"))
        alb = _num_or_none(a.get("albumin"))
        if na is None or cl is None or hco3 is None:
            return {"headline": "Enter sodium, chloride, and bicarbonate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        ag = na - (cl + hco3)
        corrected_ag = ag + 2.5 * (4.0 - alb) if alb is not None else ag
        flags = []
        sev = "good"
        if hco3 < 22:
            flags.append({"text": "Bicarbonate <22 mmol/L - KDIGO suggests considering oral bicarbonate supplementation in CKD to keep bicarbonate within the normal range.", "severity": "caution"})
            sev = "caution"
        if corrected_ag > 12:
            flags.append({"text": "Elevated (corrected) anion gap - evaluate for an anion-gap process (e.g., uremia, lactic acidosis, ketoacidosis, toxic ingestion) rather than assuming a purely hyperchloremic picture.", "severity": "warning"})
            sev = "warning"
        metrics = [{"label": "Anion gap", "value": round(ag, 1)}]
        if alb is not None:
            metrics.append({"label": "Corrected AG", "value": round(corrected_ag, 1)})
        metrics.append({"label": "Bicarbonate", "value": hco3, "unit": "mmol/L"})
        return {
            "headline": f"Anion gap {corrected_ag:.1f}{' (albumin-corrected)' if alb is not None else ''}",
            "headlineSeverity": sev,
            "metrics": metrics,
            "flags": flags,
            "notes": "Anion gap = Na - (Cl + HCO3); albumin correction adds ~2.5 mmol/L per 1 g/dL albumin below 4.0 g/dL. Normal AG varies by assay (commonly ~8-12 mmol/L) - use your lab's reference range.",
        }


class CINRiskCalculator(Calculator):
    key = "cin_risk"

    def compute(self, a: dict) -> dict:
        pts = 0
        if a.get("hypotension") == "yes":
            pts += 5
        if a.get("iabp") == "yes":
            pts += 5
        if a.get("chf") == "yes":
            pts += 5
        age = _num_or_none(a.get("age"))
        if age is not None and age > 75:
            pts += 4
        if a.get("anemia") == "yes":
            pts += 3
        if a.get("diabetes") == "yes":
            pts += 3
        vol = _num_or_none(a.get("contrastVolumeML"))
        if vol is not None:
            pts += int(vol // 100)
        egfr = _num_or_none(a.get("egfr"))
        if egfr is not None:
            if egfr < 20:
                pts += 6
            elif egfr < 40:
                pts += 4
            elif egfr < 60:
                pts += 2
        else:
            cr = _num_or_none(a.get("creatinine"))
            if cr is not None and cr > 1.5:
                pts += 4
        if pts <= 5:
            category, sev = "Low risk", "good"
        elif pts <= 10:
            category, sev = "Moderate risk", "caution"
        elif pts <= 15:
            category, sev = "High risk", "warning"
        else:
            category, sev = "Very high risk", "critical"
        flags = []
        if sev != "good":
            flags.append({"text": "Consider IV isotonic fluids, minimizing contrast volume, holding nephrotoxic agents, and post-procedure creatinine monitoring.", "severity": sev})
        return {
            "headline": f"{category} (score {pts})",
            "headlineSeverity": sev,
            "metrics": [{"label": "Risk score", "value": pts}],
            "flags": flags,
            "notes": "Reproduces the structure of the published Mehran (2004) contrast-nephropathy risk score. Point weights are reproduced from memory of the published tool - cross-check against the original publication or your institution's protocol before using for a specific high-stakes contrast decision.",
        }


class PLASMICScoreCalculator(Calculator):
    key = "plasmic_score"

    def compute(self, a: dict) -> dict:
        pts = 0
        plt = _num_or_none(a.get("platelets"))
        if plt is not None and plt < 30:
            pts += 1
        if a.get("hemolysisEvidence") == "yes":
            pts += 1
        if a.get("activeCancer") == "no":
            pts += 1
        if a.get("transplantHistory") == "no":
            pts += 1
        mcv = _num_or_none(a.get("mcv"))
        if mcv is not None and mcv < 90:
            pts += 1
        inr = _num_or_none(a.get("inr"))
        if inr is not None and inr < 1.5:
            pts += 1
        cr = _num_or_none(a.get("creatinine"))
        if cr is not None and cr < 2.0:
            pts += 1
        if pts <= 4:
            category, sev = "Low risk", "good"
        elif pts == 5:
            category, sev = "Intermediate risk", "caution"
        else:
            category, sev = "High risk", "warning"
        flags = []
        if sev != "good":
            flags.append({"text": "Higher PLASMIC score raises suspicion for TTP - consider urgent ADAMTS13 testing and empiric plasma exchange while awaiting results if clinical suspicion is high.", "severity": sev})
        return {
            "headline": f"{category} - score {pts}/7",
            "headlineSeverity": sev,
            "metrics": [{"label": "PLASMIC score", "value": f"{pts} / 7"}],
            "flags": flags,
            "notes": "Reproduces the structure of the published PLASMIC score (Bendapudi et al.) for predicting severe ADAMTS13 deficiency in suspected thrombotic microangiopathy. Point criteria reproduced from memory - cross-check against the original publication before using for an urgent plasma-exchange decision.",
        }


class DiabetesMedRenalSafetyCalculator(Calculator):
    key = "diabetes_med_renal_safety"

    def compute(self, a: dict) -> dict:
        egfr = _num_or_none(a.get("egfr"))
        flags = []
        sev = "good"
        if a.get("onMetformin") == "yes" and egfr is not None:
            if egfr < 30:
                flags.append({"text": "Metformin is contraindicated at eGFR <30 mL/min/1.73m\u00b2 (FDA labeling).", "severity": "critical"})
                sev = "critical"
            elif egfr < 45:
                flags.append({"text": "Metformin: use caution and consider dose reduction at eGFR 30-44; do not initiate new metformin in this range per FDA labeling.", "severity": "warning"})
                if sev != "critical":
                    sev = "warning"
        if a.get("onSglt2i") == "yes" and egfr is not None and egfr < 20:
            flags.append({"text": "Most SGLT2 inhibitors are not recommended below eGFR ~20 for glycemic benefit (kidney/heart-failure indications may differ) - confirm against the specific agent's current label, as thresholds have shifted downward with newer approvals.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        if a.get("onSulfonylurea") == "yes" and egfr is not None and egfr < 60:
            flags.append({"text": "Sulfonylureas carry increased hypoglycemia risk as eGFR falls - glyburide in particular is often avoided in CKD; glipizide/glimepiride may be preferred with dose caution.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"{len(flags)} concern(s) flagged" if flags else "No concerns flagged from entries",
            "headlineSeverity": sev,
            "metrics": [{"label": "eGFR", "value": egfr, "unit": "mL/min/1.73m\u00b2"}] if egfr is not None else [],
            "flags": flags,
            "notes": "Covers only metformin, SGLT2 inhibitors, and sulfonylureas - the three most common renally-relevant diabetes medication decisions in nephrology. Verify against the current product label for the specific agent, especially for SGLT2 inhibitors.",
        }


class CKDStagingCalculator(Calculator):
    key = "ckd_staging"

    # Standard KDIGO 2012 G-stage x A-stage heat map, encoded as an explicit lookup
    # rather than derived conditionals, specifically to avoid any risk of a subtle
    # off-by-one error reproducing a widely-referenced clinical grid from memory.
    RISK_GRID = {
        ("G1", "A1"): ("good", "Low risk"), ("G1", "A2"): ("caution", "Moderately increased risk"), ("G1", "A3"): ("warning", "High risk"),
        ("G2", "A1"): ("good", "Low risk"), ("G2", "A2"): ("caution", "Moderately increased risk"), ("G2", "A3"): ("warning", "High risk"),
        ("G3a", "A1"): ("caution", "Moderately increased risk"), ("G3a", "A2"): ("warning", "High risk"), ("G3a", "A3"): ("critical", "Very high risk"),
        ("G3b", "A1"): ("warning", "High risk"), ("G3b", "A2"): ("critical", "Very high risk"), ("G3b", "A3"): ("critical", "Very high risk"),
        ("G4", "A1"): ("critical", "Very high risk"), ("G4", "A2"): ("critical", "Very high risk"), ("G4", "A3"): ("critical", "Very high risk"),
        ("G5", "A1"): ("critical", "Very high risk"), ("G5", "A2"): ("critical", "Very high risk"), ("G5", "A3"): ("critical", "Very high risk"),
    }
    DIPSTICK_TO_A_CATEGORY = {"negative": "A1", "trace": "A1", "1+": "A2", "2+": "A3", "3+": "A3"}

    def _calc_egfr_ckdepi2021(self, scr: float, age: float, sex: str) -> float:
        kappa = 0.7 if sex == "female" else 0.9
        alpha = -0.241 if sex == "female" else -0.302
        ratio = scr / kappa
        min_r, max_r = min(ratio, 1), max(ratio, 1)
        egfr = 142 * (min_r ** alpha) * (max_r ** -1.200) * (0.9938 ** age)
        if sex == "female":
            egfr *= 1.012
        return round(egfr * 10) / 10

    def _g_stage(self, egfr: float) -> str:
        if egfr >= 90:
            return "G1"
        if egfr >= 60:
            return "G2"
        if egfr >= 45:
            return "G3a"
        if egfr >= 30:
            return "G3b"
        if egfr >= 15:
            return "G4"
        return "G5"

    def _a_stage(self, acr: float) -> str:
        if acr < 30:
            return "A1"
        if acr <= 300:
            return "A2"
        return "A3"

    def compute(self, a: dict) -> dict:
        # eGFR: a directly reported value takes priority; otherwise calculate from
        # creatinine + age + sex via CKD-EPI 2021 (race-free), exactly as the original
        # adaptive wizard does when a lab-reported eGFR isn't available.
        egfr = _num_or_none(a.get("egfrValue")) if a.get("knownEgfr") == "yes" else None
        egfr_source = "reported"
        if egfr is None and a.get("knownEgfr") == "no":
            scr, age = _num_or_none(a.get("scrValue")), _num_or_none(a.get("age"))
            sex = a.get("sex")
            if scr and age and sex:
                egfr = self._calc_egfr_ckdepi2021(scr, age, sex)
                egfr_source = "calculated (CKD-EPI 2021, race-free)"
        # Fallback: allow direct egfr/acr keys too, for simple non-wizard callers.
        if egfr is None:
            egfr = _num_or_none(a.get("egfr"))

        acr = None
        a_cat = None
        acr_source = "reported"
        if a.get("knownAcr") == "yes":
            acr = _num_or_none(a.get("acrValue"))
            if acr is not None:
                a_cat = self._a_stage(acr)
        elif a.get("knownAcr") == "no" and a.get("dipstickProtein"):
            a_cat = self.DIPSTICK_TO_A_CATEGORY.get(a.get("dipstickProtein"), "A2")
            acr_source = "estimated from urine dipstick"
        if a_cat is None:
            acr = _num_or_none(a.get("acr"))
            if acr is not None:
                a_cat = self._a_stage(acr)

        if egfr is None or a_cat is None:
            return {"headline": "Enter eGFR (or creatinine/age/sex) and ACR (or dipstick) to stage.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}

        g = self._g_stage(egfr)
        sev, risk_label = self.RISK_GRID[(g, a_cat)]

        flags = []
        if sev == "critical":
            flags.append({"text": "Very high risk on the KDIGO heat map - nephrology referral and RRT/transplant planning discussion are generally appropriate at this combination of G and A stage.", "severity": "critical"})
        elif sev == "warning":
            flags.append({"text": "High risk on the KDIGO heat map - nephrology referral is generally appropriate.", "severity": "warning"})

        # Referral flags, mirroring the original wizard's rule-based referral logic.
        reasons = []
        urgency = "routine"
        if egfr < 30:
            reasons.append("eGFR below 30 mL/min/1.73m\u00b2 (CKD G4\u2013G5)")
        if acr is not None and acr >= 300:
            reasons.append("ACR \u2265300 mg/g (severely increased albuminuria)")
        prior_egfr = _num_or_none(a.get("priorEgfr"))
        if prior_egfr and prior_egfr > 0:
            if (prior_egfr - egfr) / prior_egfr >= 0.25:
                reasons.append("sustained eGFR decline \u226525% from prior value")
        antihtn = _num_or_none(a.get("antihtnCount"))
        if antihtn is not None and antihtn >= 4:
            reasons.append("hypertension on \u22654 antihypertensive classes (treatment-resistant)")
        potassium = _num_or_none(a.get("potassium"))
        if potassium is not None and (potassium < 3.5 or potassium > 5.5):
            reasons.append("persistent serum potassium abnormality")
        if "akiHistory" in _list(a.get("riskFactors")):
            reasons.append("history of acute kidney injury on CKD")

        if egfr < 15:
            urgency = "urgent"
        elif potassium is not None and (potassium < 3.0 or potassium > 6.0):
            urgency = "urgent"
        elif reasons:
            urgency = "soon"

        if reasons:
            flags.append({"text": f"Referral flags ({urgency}): {'; '.join(reasons)}.", "severity": "critical" if urgency == "urgent" else "warning"})

        return {
            "headline": f"CKD {g}{a_cat} - {risk_label}",
            "headlineSeverity": sev,
            "metrics": [
                {"label": "eGFR", "value": egfr, "unit": f"mL/min/1.73m\u00b2 ({egfr_source})"},
                {"label": "G-stage", "value": g},
                {"label": "ACR", "value": acr if acr is not None else acr_source, "unit": "mg/g" if acr is not None else ""},
                {"label": "A-stage", "value": a_cat},
            ],
            "flags": flags,
            "notes": "Based on the standard KDIGO 2012 CKD classification grid combining eGFR category (G1-G5, with G3 split into G3a/G3b) and albuminuria category (A1-A3), with the same eGFR-from-creatinine (CKD-EPI 2021, race-free) and referral-flag logic as the original adaptive assessment. The AI-generated narrative care plan from the original tool is a separate feature not included here.",
        }
