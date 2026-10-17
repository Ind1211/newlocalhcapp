from app.calculators.base import Calculator


def _num_or_none(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


class DialysisStartReadinessCalculator(Calculator):
    key = "dialysis_start_readiness"

    def compute(self, a: dict) -> dict:
        egfr = _num_or_none(a.get("egfr"))
        sym = [s for s in _list(a.get("symptoms")) if s != "none"]
        refractory_count = sum(1 for k in ["refractoryVolumeOverload", "refractoryHyperkalemia", "refractoryAcidosis"] if a.get(k) == "yes")
        flags = []
        sev = "good"
        if len(sym) > 0:
            flags.append({"text": "Uremic symptom(s) present - per KDOQI/KDIGO guidance, dialysis initiation is generally based on signs/symptoms of uremia rather than a fixed eGFR threshold.", "severity": "warning"})
            sev = "warning"
        if refractory_count > 0:
            flags.append({"text": "Refractory metabolic/volume complication(s) present - an indication to initiate dialysis regardless of eGFR.", "severity": "critical"})
            sev = "critical"
        if egfr is not None and egfr < 15 and len(sym) == 0 and refractory_count == 0:
            flags.append({"text": "eGFR <15 without symptoms or refractory issues - many guidelines support planned, individualized timing; use this window for access planning and shared decision-making.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": "Indications present to initiate dialysis now" if sev == "critical" else ("Uremic symptoms present - dialysis initiation likely indicated" if sev == "warning" else "No urgent indication identified from entries"),
            "headlineSeverity": sev,
            "metrics": [{"label": "eGFR", "value": egfr, "unit": "mL/min/1.73m\u00b2"}] if egfr is not None else [],
            "flags": flags,
            "notes": "KDOQI/KDIGO guidance emphasizes starting dialysis based on signs/symptoms of uremia, refractory complications, or declining nutritional/functional status - not a single fixed eGFR cutoff. This tool structures that judgment; it does not replace it.",
        }


class UrinalysisInterpreterCalculator(Calculator):
    key = "urinalysis_interpreter"

    def compute(self, a: dict) -> dict:
        flags = []
        pattern = None
        if a.get("rbcCasts") == "yes" or a.get("dysmorphicRbc") == "yes":
            pattern = "Glomerular bleeding pattern"
            flags.append({"text": "RBC casts and/or dysmorphic RBCs suggest a glomerular source of hematuria - evaluate for glomerulonephritis.", "severity": "warning"})
        if a.get("muddyBrownCasts") == "yes":
            pattern = (pattern + " + tubular injury pattern") if pattern else "Tubular injury pattern (muddy brown casts)"
            flags.append({"text": "Muddy brown/granular casts are classic for acute tubular necrosis.", "severity": "warning"})
        if a.get("wbcCasts") == "yes":
            pattern = (pattern + " + interstitial/pyelonephritis pattern") if pattern else "Interstitial/pyelonephritis pattern (WBC casts)"
            flags.append({"text": "WBC casts suggest pyelonephritis or interstitial nephritis rather than lower urinary tract infection alone.", "severity": "caution"})
        if a.get("eosinophils") == "yes":
            flags.append({"text": "Urine eosinophils have historically been associated with acute interstitial nephritis, though sensitivity/specificity are limited - interpret alongside clinical context (e.g., new drug exposure).", "severity": "caution"})
        if a.get("crystals") and a.get("crystals") != "none":
            flags.append({"text": f"{a.get('crystals')} crystals noted - correlate with stone risk/metabolic workup if recurrent.", "severity": "caution"})
        if not pattern:
            pattern = "No strong glomerular/tubular/interstitial pattern flagged from entries"
        return {
            "headline": pattern,
            "headlineSeverity": "warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good"),
            "metrics": [],
            "flags": flags,
            "notes": "A structured pattern-recognition aid, not a substitute for formally read urine microscopy by an experienced observer - cast and crystal identification has real inter-observer variability.",
        }


class DiabeticKidneyScreeningCalculator(Calculator):
    key = "diabetic_kidney_screening"

    def compute(self, a: dict) -> dict:
        if not a.get("diabetesType"):
            return {"headline": "Select diabetes type.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        years = _num_or_none(a.get("yearsSinceDiagnosis"))
        screening_due = a.get("diabetesType") == "type2" or (years is not None and years >= 5)
        if not screening_due:
            return {
                "headline": "Screening not yet due", "headlineSeverity": "good", "metrics": [],
                "flags": [{"text": "Type 1 diabetes: annual ACR/eGFR screening is generally recommended starting 5 years after diagnosis (or at puberty, if earlier).", "severity": "caution"}],
                "notes": "Per ADA/KDIGO diabetes-CKD guidance.",
            }
        acr_ago = _num_or_none(a.get("lastAcrScreenMonthsAgo"))
        egfr_ago = _num_or_none(a.get("lastEgfrMonthsAgo"))
        flags = []
        sev = "good"
        if acr_ago is None or acr_ago > 12:
            flags.append({"text": "Annual urine ACR screening appears overdue (or has never been recorded) - recommended yearly once screening has started.", "severity": "warning"})
            sev = "warning"
        if egfr_ago is None or egfr_ago > 12:
            flags.append({"text": "Annual eGFR screening appears overdue (or has never been recorded).", "severity": "warning"})
            sev = "warning"
        return {
            "headline": "Screening appears up to date" if sev == "good" else "Screening appears overdue",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Per ADA/KDIGO diabetes-CKD guidance: annual ACR and eGFR for Type 2 diabetes from diagnosis, and for Type 1 diabetes starting 5 years after diagnosis.",
        }


class PostObstructiveDiuresisCalculator(Calculator):
    key = "post_obstructive_diuresis"

    def compute(self, a: dict) -> dict:
        uo = _num_or_none(a.get("urineOutputMlPerHr"))
        if uo is None:
            return {"headline": "Enter urine output rate.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        sev, tier = "good", "Normal post-decompression diuresis"
        if uo > 200:
            tier, sev = "Significant post-obstructive diuresis", "warning"
        elif uo > 100:
            tier, sev = "Mild-moderate post-obstructive diuresis", "caution"
        flags = []
        if sev != "good":
            flags.append({"text": "Match fluid replacement to roughly half the hourly urine output (typically with 0.45% saline, adjusted to electrolytes) rather than 1:1, to avoid perpetuating the diuresis while still preventing volume depletion.", "severity": "warning"})
            flags.append({"text": "Check electrolytes (sodium, potassium, magnesium) every 4-6 hours until the diuresis resolves.", "severity": "warning"})
        na, k = _num_or_none(a.get("sodium")), _num_or_none(a.get("potassium"))
        if na is not None and na > 145:
            flags.append({"text": "Hypernatremia - free water losses often exceed sodium losses in post-obstructive diuresis; adjust replacement fluid tonicity accordingly.", "severity": "caution"})
        if k is not None and k < 3.5:
            flags.append({"text": "Hypokalemia - common with brisk diuresis; replace as needed.", "severity": "caution"})
        return {
            "headline": f"{tier} ({uo} mL/hr)", "headlineSeverity": sev,
            "metrics": [{"label": "Urine output", "value": uo, "unit": "mL/hr"}], "flags": flags,
            "notes": "Post-obstructive diuresis is usually a physiologic (appropriate) excretion of retained fluid/solute rather than a pathologic process, but can cause volume depletion or electrolyte derangement if under- or over-replaced. The >200 mL/hr \"significant\" threshold is a commonly cited rule of thumb, not a rigid cutoff.",
        }


class ObstructiveUropathyGradingCalculator(Calculator):
    key = "obstructive_uropathy_grading"

    def compute(self, a: dict) -> dict:
        sev, urgency = "good", "Routine evaluation"
        if a.get("signsOfInfection") == "yes":
            urgency, sev = "Emergent decompression indicated", "critical"
        elif a.get("laterality") == "bilateral" or a.get("functioningKidneys") == "solitary-or-single-functioning":
            if a.get("hydronephrosisGrade") == "severe" or a.get("risingCreatinine") == "yes":
                urgency, sev = "Urgent decompression indicated", "critical"
            elif a.get("hydronephrosisGrade") == "moderate":
                urgency, sev = "Prompt evaluation for decompression", "warning"
        else:
            if a.get("hydronephrosisGrade") == "severe":
                urgency, sev = "Prompt evaluation for decompression", "warning"
            elif a.get("hydronephrosisGrade") == "moderate":
                urgency, sev = "Routine to prompt evaluation", "caution"
        flags = []
        if sev == "critical" and a.get("signsOfInfection") == "yes":
            flags.append({"text": "Infected obstructed system (pyonephrosis) is a urologic emergency - emergent decompression (nephrostomy or stent) plus antibiotics; do not delay for a full workup.", "severity": "critical"})
        elif sev == "critical":
            flags.append({"text": "Bilateral or solitary-kidney obstruction with severe hydronephrosis/rising creatinine - urgent decompression to preserve renal function.", "severity": "critical"})
        elif sev == "warning":
            flags.append({"text": "Consider prompt urology consultation for decompression (stent or nephrostomy) depending on the cause and level of obstruction.", "severity": "warning"})
        return {
            "headline": urgency, "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Urgency depends on both the severity/laterality of obstruction and functional reserve - bilateral or solitary-kidney obstruction has far less reserve than unilateral obstruction with a normal contralateral kidney. Infected obstruction is always urgent regardless of hydronephrosis grade.",
        }


class VolumeStatusCalculator(Calculator):
    key = "volume_status"

    def compute(self, a: dict) -> dict:
        overload, depletion = 0, 0
        try:
            edema_grade = int(a.get("edemaGrade") or "0")
        except (TypeError, ValueError):
            edema_grade = 0
        if edema_grade >= 2:
            overload += 1
        if a.get("jvpElevated") == "yes":
            overload += 1
        if a.get("dyspneaOrthopnea") == "yes":
            overload += 1
        wg, wd = _num_or_none(a.get("weightGainKg")), _num_or_none(a.get("weightGainDays"))
        if wg is not None and wd is not None and wd > 0 and wg / wd >= 0.5:
            overload += 1
        if a.get("intradialyticHypotension") == "yes":
            depletion += 1
        bis = None
        if a.get("haveBis") == "yes":
            bis = _num_or_none(a.get("bisOverloadL"))
            if bis is not None:
                if bis > 1.5:
                    overload += 2
                elif bis < 0:
                    depletion += 2
        flags = []
        if depletion > overload and depletion >= 1:
            status, sev = "Signals suggest possible volume depletion", "caution"
            flags.append({"text": "Consider a trial reduction in ultrafiltration target / antihypertensive review.", "severity": "caution"})
        elif overload >= 2:
            status, sev = "Signals suggest likely fluid overload", "warning"
            flags.append({"text": "Consider trialing a lower dry weight and reviewing sodium/fluid intake.", "severity": "warning"})
        elif overload == 1:
            status, sev = "Mild signal of fluid excess - monitor", "caution"
        else:
            status, sev = "No strong signal of overload or depletion by exam", "good"
        metrics = [{"label": "Overload signals", "value": overload}, {"label": "Depletion signals", "value": depletion}]
        if bis is not None:
            metrics.append({"label": "BIS overload", "value": bis, "unit": "L"})
        return {
            "headline": status, "headlineSeverity": sev, "metrics": metrics, "flags": flags,
            "notes": "A structured bedside composite, not a validated standalone instrument. Bioimpedance is the most objective single input if available; trends across sessions matter more than one reading.",
        }


class PDPeritonitisCalculator(Calculator):
    key = "pd_peritonitis"

    def compute(self, a: dict) -> dict:
        criteria = 0
        if a.get("cloudyEffluent") == "yes" or a.get("abdominalPain") == "yes":
            criteria += 1
        wbc, neut = _num_or_none(a.get("effluentWbc")), _num_or_none(a.get("effluentNeutrophilPct"))
        if wbc is not None and wbc > 100 and (neut is None or neut >= 50):
            criteria += 1
        if a.get("positiveCulture") == "yes":
            criteria += 1
        meets = criteria >= 2
        flags = [
            {"text": "Meets ISPD criteria for PD-associated peritonitis - start empiric intraperitoneal antibiotics per local protocol pending final culture results.", "severity": "critical"}
            if meets else
            {"text": "Does not yet meet 2-of-3 ISPD criteria - consider repeat effluent cell count/culture and close follow-up if clinical suspicion remains.", "severity": "caution"}
        ]
        return {
            "headline": "Meets ISPD peritonitis diagnostic criteria" if meets else "Criteria not yet met",
            "headlineSeverity": "critical" if meets else "caution",
            "metrics": [{"label": "Criteria met", "value": f"{criteria} / 3"}], "flags": flags,
            "notes": "Based on ISPD peritonitis diagnostic criteria (\u22652 of: clinical features, effluent WBC >100/\u00b5L with >50% neutrophils, positive effluent culture). Culture-negative peritonitis is still diagnosed if the other two criteria are met.",
        }


class PretxReadinessCalculator(Calculator):
    key = "pretx_readiness"

    def compute(self, a: dict) -> dict:
        items = ["cardiacClearance", "hlaTyping", "malignancyScreening", "infectionScreening", "psychosocialEval"]
        labels = {"cardiacClearance": "Cardiac clearance", "hlaTyping": "HLA typing/crossmatch", "malignancyScreening": "Malignancy screening", "infectionScreening": "Infection screening", "psychosocialEval": "Psychosocial evaluation"}
        outstanding = [k for k in items if a.get(k) != "yes"]
        pct = round(((len(items) - len(outstanding)) / len(items)) * 100)
        flags = [{"text": labels[k] + " not yet confirmed complete.", "severity": "caution"} for k in outstanding]
        bmi = _num_or_none(a.get("bmi"))
        if bmi is not None and bmi >= 40:
            flags.append({"text": "BMI \u226540 - many programs require weight optimization before listing; confirm local threshold.", "severity": "warning"})
        if a.get("smokingStatus") == "current":
            flags.append({"text": "Active smoking - most transplant programs require cessation prior to listing.", "severity": "warning"})
        return {
            "headline": "All standard screening items confirmed complete" if len(outstanding) == 0 else f"{len(outstanding)} screening item(s) outstanding",
            "headlineSeverity": "good" if len(outstanding) == 0 else ("warning" if len(outstanding) >= 3 else "caution"),
            "metrics": [{"label": "Checklist complete", "value": pct, "unit": "%"}], "flags": flags,
            "notes": "Reflects commonly required pre-transplant workup domains; exact requirements vary by transplant center and organ allocation system - confirm against your program's protocol.",
        }


class PosttxMonitoringCalculator(Calculator):
    key = "posttx_monitoring"

    def compute(self, a: dict) -> dict:
        months = _num_or_none(a.get("monthsPostTx")) or 0
        rng = [8, 12] if months <= 3 else ([6, 10] if months <= 12 else [4, 8])
        tac = _num_or_none(a.get("tacLevel"))
        flags = []
        sev = "good"
        if tac is not None and (tac < rng[0] or tac > rng[1]):
            flags.append({"text": f"Trough outside the typical {rng[0]}\u2013{rng[1]} ng/mL target for this post-transplant period (center protocols vary).", "severity": "warning"})
            sev = "warning"
        if a.get("dsaPositive") == "yes":
            flags.append({"text": "DSA positive - increased rejection risk; correlate with graft function and consider biopsy.", "severity": "warning"})
            sev = "warning"
        if a.get("creatinineTrend") == "rising":
            flags.append({"text": "Rising creatinine - evaluate for rejection, infection, or drug toxicity.", "severity": "warning"})
            sev = "warning"
        sym = _list(a.get("symptoms"))
        if any(s != "none" for s in sym):
            flags.append({"text": "Symptoms present that can indicate rejection or infection - same-day transplant team evaluation warranted.", "severity": "critical"})
            sev = "critical"
        if len(flags) == 0:
            return {"headline": "No concerning signals from the values entered", "headlineSeverity": "good", "metrics": [{"label": "Tac target range", "value": f"{rng[0]}\u2013{rng[1]}", "unit": "ng/mL"}], "flags": [], "notes": "Immunosuppression targets vary substantially by center, agent, and regimen - treat ranges as general reference only."}
        return {
            "headline": "Findings warrant prompt transplant team review" if sev == "critical" else "One or more values outside expected range",
            "headlineSeverity": sev,
            "metrics": [{"label": "Tac target range", "value": f"{rng[0]}\u2013{rng[1]}", "unit": "ng/mL"}, {"label": "Reported trough", "value": tac if tac is not None else "\u2014", "unit": "ng/mL"}],
            "flags": flags,
            "notes": "Immunosuppression targets vary substantially by transplant center, agent, and combination regimen - treat these ranges as general reference only.",
        }


class LivingDonorEvalCalculator(Calculator):
    key = "living_donor_eval"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        egfr = _num_or_none(a.get("donorEgfr"))
        if egfr is not None and egfr < 80:
            flags.append({"text": "Donor eGFR below the commonly used ~80 mL/min/1.73m\u00b2 general threshold - confirm against program-specific, age-adjusted norms.", "severity": "warning"})
            sev = "warning"
        acr = _num_or_none(a.get("donorAcr"))
        if acr is not None and acr >= 30:
            flags.append({"text": "Albuminuria present - generally a contraindication to donation pending further workup.", "severity": "warning"})
            sev = "warning"
        if a.get("donorBp") == "uncontrolled":
            flags.append({"text": "Uncontrolled BP - most programs require control (and many exclude candidates needing multiple agents) before donation.", "severity": "warning"})
            sev = "warning"
        screening_labels = {"diabetesScreening": "Diabetes", "malignancyScreening": "Malignancy", "psychosocialEval": "Psychosocial"}
        for k, label in screening_labels.items():
            if a.get(k) != "yes":
                flags.append({"text": f"{label} screening not yet confirmed complete.", "severity": "caution"})
                if sev == "good":
                    sev = "caution"
        if a.get("pregnancy") == "yes":
            flags.append({"text": "Currently pregnant - donation is deferred until well after pregnancy.", "severity": "warning"})
            sev = "warning"
        bmi = _num_or_none(a.get("bmi"))
        if bmi is not None and bmi >= 35:
            flags.append({"text": "BMI \u226535 - many programs require weight optimization or decline donation at this BMI.", "severity": "warning"})
            sev = "warning"
        if a.get("geneticallyRelated") == "yes":
            flags.append({"text": "Biologically related donor - consider APOL1 testing where ancestry-relevant, given implications for donor long-term risk and recipient graft outcomes.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"{len(flags)} item(s) to resolve before donation clearance" if flags else "No major issues flagged from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Donor eligibility thresholds (eGFR, BMI, BP) vary meaningfully by transplant program and are often age/sex-adjusted - treat this as a starting checklist, not a final eligibility determination.",
        }


class TransplantRejectionClassifierCalculator(Calculator):
    key = "transplant_rejection_classifier"

    def compute(self, a: dict) -> dict:
        tcmr = False
        if a.get("arteritis") == "yes" or a.get("tubulitis") == "severe" or (a.get("tubulitis") == "moderate" and a.get("interstitialInflammation") and a.get("interstitialInflammation") != "none"):
            tcmr = True
        elif a.get("tubulitis") and a.get("tubulitis") != "none" and a.get("interstitialInflammation") and a.get("interstitialInflammation") != "none":
            tcmr = "borderline"
        amr = a.get("dsaPositive") == "yes" and (a.get("c4dPositive") == "yes" or a.get("peritubularCapillaritis") == "yes" or a.get("glomerulitis") == "yes")
        flags = []
        if tcmr is True and amr:
            headline, sev = "Mixed features suggesting both TCMR and AMR", "critical"
            flags.append({"text": "Mixed rejection pattern - typically warrants both anti-T-cell therapy (e.g., pulse steroids \u00b1 thymoglobulin) and antibody-directed therapy (e.g., plasmapheresis/IVIG) per center protocol.", "severity": "critical"})
        elif tcmr is True:
            headline, sev = "Features suggestive of T-cell mediated rejection (TCMR)", "warning"
            flags.append({"text": "Consider pulse corticosteroids \u00b1 T-cell-depleting therapy for higher-grade TCMR, per Banff grade and center protocol.", "severity": "warning"})
        elif amr:
            headline, sev = "Features suggestive of antibody-mediated rejection (AMR)", "warning"
            flags.append({"text": "Consider plasmapheresis, IVIG, and/or anti-B-cell/complement-directed therapy per center protocol; correlate with DSA titer trend.", "severity": "warning"})
        elif tcmr == "borderline":
            headline, sev = "Borderline changes - not diagnostic of rejection", "caution"
            flags.append({"text": "Borderline changes may or may not need treatment depending on clinical context (graft function trend, DSA status) - many centers treat borderline changes accompanied by graft dysfunction.", "severity": "caution"})
        else:
            headline, sev = "No strong histologic features of rejection from entries", "good"
        return {
            "headline": headline, "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "A heavily simplified guide inspired by the Banff classification framework for kidney transplant rejection (T-cell-mediated vs. antibody-mediated features). The Banff schema is complex, revised periodically, and formally requires a trained transplant pathologist's full biopsy scoring - this tool is for structuring discussion, not diagnosis.",
        }


class BKVirusNephropathyCalculator(Calculator):
    key = "bk_virus_nephropathy"

    def compute(self, a: dict) -> dict:
        viremia = _num_or_none(a.get("bkViremiaCopiesPerMl"))
        flags = []
        if a.get("biopsySv40Positive") == "yes":
            headline, sev = "Biopsy-proven BK virus nephropathy", "critical"
            flags.append({"text": "Reduce immunosuppression (typically the antimetabolite first, then the calcineurin inhibitor) as the primary treatment; monitor viral load and graft function closely.", "severity": "critical"})
        elif viremia is not None and viremia >= 10000:
            headline, sev = "High-level BK viremia - presumptive BK nephropathy", "warning"
            flags.append({"text": "Sustained viral loads in this range are often used as a threshold to reduce immunosuppression preemptively and consider biopsy to confirm nephropathy.", "severity": "warning"})
        elif viremia is not None and viremia >= 1000:
            headline, sev = "Significant BK viremia - increase monitoring", "caution"
            flags.append({"text": "Increase monitoring frequency (viral load every 2-4 weeks) and consider a modest reduction in immunosuppression depending on trend.", "severity": "caution"})
        else:
            headline, sev = "No high-level viremia or biopsy-proven nephropathy from entries", "good"
        if a.get("recentAntirejectionTx") == "yes":
            flags.append({"text": "Recent treatment for rejection increases BK reactivation risk - heightened surveillance is reasonable for the following months.", "severity": "caution"})
        if a.get("risingCreatinine") == "yes" and sev != "critical":
            flags.append({"text": "Rising creatinine alongside viremia raises concern for nephropathy - consider biopsy to distinguish BK nephropathy from rejection (they can coexist).", "severity": "warning"})
        return {
            "headline": headline, "headlineSeverity": sev,
            "metrics": [{"label": "BK viral load", "value": viremia, "unit": "copies/mL"}] if viremia is not None else [],
            "flags": flags,
            "notes": "BK viremia screening is typically performed periodically in the first post-transplant year. Exact viral-load thresholds for action vary by center/assay - treat the numbers here as commonly cited reference points, not a fixed protocol.",
        }


class CMVRiskStratificationCalculator(Calculator):
    key = "cmv_risk_stratification"

    def compute(self, a: dict) -> dict:
        if not a.get("donorCmvStatus") or not a.get("recipientCmvStatus"):
            return {"headline": "Select donor and recipient CMV status.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if a["donorCmvStatus"] == "positive" and a["recipientCmvStatus"] == "negative":
            risk_category, sev = "High risk (D+/R\u2212)", "warning"
        elif a["recipientCmvStatus"] == "positive":
            risk_category, sev = "Intermediate risk (R+)", "caution"
        else:
            risk_category, sev = "Low risk (D\u2212/R\u2212)", "good"
        flags = []
        if risk_category.startswith("High"):
            flags.append({"text": "D+/R\u2212 is the highest-risk serostatus combination - most protocols recommend extended prophylaxis (often 6 months or longer) rather than pre-emptive monitoring alone.", "severity": "warning"})
        if a.get("lymphocyteDepletingInduction") == "yes":
            flags.append({"text": "Lymphocyte-depleting induction further increases CMV risk - reinforces the case for prophylaxis (or a longer course) regardless of serostatus.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if a.get("currentProphylaxis") == "none" and sev != "good":
            flags.append({"text": "No current CMV prophylaxis despite an elevated-risk profile - confirm this is an intentional pre-emptive monitoring strategy rather than an oversight.", "severity": "warning"})
            sev = "warning"
        return {
            "headline": risk_category, "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "CMV risk stratification is primarily driven by donor/recipient serostatus (highest risk when donor-positive, recipient-negative) and induction intensity. Prophylaxis duration and pre-emptive monitoring strategies vary by center protocol.",
        }
