from app.calculators.base import Calculator
from app.calculators.kidney_structured_1 import _num_or_none, _list


class SGACalculator(Calculator):
    key = "sga"

    def compute(self, a: dict) -> dict:
        severe_count, mild_count = 0, 0
        wc = _num_or_none(a.get("weightChangePct"))
        if wc is not None and wc >= 10:
            severe_count += 1
        elif wc is not None and wc >= 5:
            mild_count += 1
        if a.get("dietaryIntake") == "severe":
            severe_count += 1
        elif a.get("dietaryIntake") == "mild":
            mild_count += 1
        if len([s for s in _list(a.get("giSymptoms")) if s != "none"]) >= 2:
            mild_count += 1
        if a.get("functionalCapacity") == "bedbound":
            severe_count += 1
        elif a.get("functionalCapacity") == "reduced":
            mild_count += 1
        if a.get("muscleWasting") == "severe":
            severe_count += 1
        elif a.get("muscleWasting") == "mild":
            mild_count += 1
        if a.get("fatLoss") == "severe":
            severe_count += 1
        elif a.get("fatLoss") == "mild":
            mild_count += 1
        if severe_count >= 2:
            rating, sev = "C \u2014 severely malnourished", "critical"
        elif severe_count >= 1 or mild_count >= 3:
            rating, sev = "B \u2014 mild to moderately malnourished", "warning"
        else:
            rating, sev = "A \u2014 well nourished", "good"
        flags = []
        if sev != "good":
            flags.append({"text": "Consider a renal dietitian referral and reassessing trend over time rather than a single snapshot.", "severity": "critical" if sev == "critical" else "warning"})
        return {
            "headline": f"SGA rating: {rating}", "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Adapted from the concept of Subjective Global Assessment (Detsky et al., as used in dialysis/CKD populations) - a simplified rating, not the full standardized SGA form.",
        }


class MISCalculator(Calculator):
    key = "mis"

    def compute(self, a: dict) -> dict:
        keys = [f"d{i}" for i in range(1, 11)]
        if any(a.get(k) is None for k in keys):
            return {"headline": "Score all 10 domains (0-3 each).", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        total = sum(int(a[k]) for k in keys)
        flags = []
        sev = "good"
        if total > 10:
            flags.append({"text": "Elevated composite score - consider dietitian involvement and evaluate reversible contributors (inflammation, inadequate dialysis, depression).", "severity": "warning"})
            sev = "warning"
        elif total > 5:
            sev = "caution"
        return {
            "headline": f"MIS total: {total} / 30", "headlineSeverity": sev,
            "metrics": [{"label": "Total score", "value": total, "unit": "/ 30"}], "flags": flags,
            "notes": "Ten-domain composite adapted from Kalantar-Zadeh et al. 2001. Trend over time is more informative than a single score; exact prognostic cutoffs vary by cohort.",
        }


class FrailtyCFSCalculator(Calculator):
    key = "frailty_cfs"

    def compute(self, a: dict) -> dict:
        if not a.get("cfsLevel"):
            return {"headline": "Select a level.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        lvl = int(a["cfsLevel"])
        flags = []
        sev = "good"
        if lvl >= 7:
            sev = "critical"
            flags.append({"text": "High frailty is associated with substantially worse outcomes after dialysis initiation or transplant surgery - involve geriatric/palliative input in shared decision-making.", "severity": "critical"})
        elif lvl >= 5:
            sev = "warning"
            flags.append({"text": "Moderate frailty - factor into dialysis-modality and transplant-listing conversations.", "severity": "warning"})
        return {
            "headline": f"CFS level {lvl}", "headlineSeverity": sev,
            "metrics": [{"label": "CFS level", "value": lvl}], "flags": flags,
            "notes": "Categories paraphrased from the concept of the Rockwood Clinical Frailty Scale (9-point) - a simplified adaptation for screening, not the official scale wording/graphic.",
        }


class KDQOLLiteCalculator(Calculator):
    key = "kdqol_lite"

    def compute(self, a: dict) -> dict:
        keys = ["symptomBurden", "kidneyBurden", "timeBurden", "frustration", "physicalFunction", "emotionalWellbeing"]
        if any(a.get(k) is None for k in keys):
            return {"headline": "Answer all six items.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        avg = sum(int(a[k]) for k in keys) / len(keys)
        flags = []
        sev = "good"
        if avg >= 2.5:
            flags.append({"text": "Higher reported burden - consider a dedicated quality-of-life discussion and screening for depression.", "severity": "caution"})
            sev = "caution"
        return {
            "headline": f"Average burden score: {avg:.1f} / 4", "headlineSeverity": sev,
            "metrics": [{"label": "Average score", "value": round(avg, 1), "unit": "/ 4 (higher = more burden)"}], "flags": flags,
            "notes": "This is an original, short kidney-focused wellbeing screener inspired by domains covered in KDQOL-36 - it is not the validated, licensed KDQOL-36/KDQOL-SF instrument (RAND) and has not been psychometrically tested. Use the licensed instrument for formal outcome measurement.",
        }


class PediatricNephroticSteroidResponseCalculator(Calculator):
    key = "pediatric_nephrotic_steroid_response"

    def compute(self, a: dict) -> dict:
        if a.get("achievedRemission") == "no":
            wks = _num_or_none(a.get("weeksOfDailySteroidWithoutRemission"))
            if wks is not None and wks >= 4:
                return {
                    "headline": "Steroid-resistant pattern", "headlineSeverity": "warning",
                    "metrics": [], "flags": [{"text": "No remission after \u22654 weeks of daily steroids - biopsy is generally indicated (steroid-resistant nephrotic syndrome is often not minimal change disease), and genetic testing should be considered, especially if congenital/familial or very young.", "severity": "warning"}],
                    "notes": "Based on standard pediatric nephrology definitions of steroid resistance. A calcineurin inhibitor trial is often considered after biopsy confirms a resistant histology.",
                }
            return {"headline": "Still within the initial treatment window", "headlineSeverity": "caution", "metrics": [], "flags": [{"text": "Steroid resistance isn't called until ~4-8 weeks of daily therapy without remission - continue current course and reassess.", "severity": "caution"}], "notes": ""}
        if a.get("relapseDuringTaperOrWithin2Wk") == "yes":
            return {
                "headline": "Steroid-dependent pattern", "headlineSeverity": "warning",
                "metrics": [], "flags": [{"text": "Relapsing during taper or shortly after stopping steroids defines steroid dependence - consider a steroid-sparing agent (e.g., levamisole, mycophenolate, calcineurin inhibitor, or rituximab) to reduce cumulative steroid exposure.", "severity": "warning"}],
                "notes": "Steroid-dependent and frequently-relapsing disease are generally managed similarly, with steroid-sparing agents considered to limit growth suppression and other steroid toxicity.",
            }
        r6, r12 = _num_or_none(a.get("relapsesIn6Months")), _num_or_none(a.get("relapsesIn12Months"))
        flags = []
        if (r6 is not None and r6 >= 2) or (r12 is not None and r12 >= 4):
            headline, sev = "Frequent relapser pattern", "warning"
            flags.append({"text": "Frequent relapses (\u22652 in 6 months, or \u22654 in 12 months) - consider a steroid-sparing agent to reduce cumulative steroid burden.", "severity": "warning"})
        elif (r6 is not None and r6 >= 1) or (r12 is not None and r12 >= 1):
            headline, sev = "Infrequent relapser pattern", "caution"
            flags.append({"text": "Occasional relapses are common and often still managed with steroids alone, tapered by response.", "severity": "caution"})
        else:
            headline, sev = "Steroid-sensitive, sustained remission", "good"
        return {"headline": headline, "headlineSeverity": sev, "metrics": [], "flags": flags, "notes": "Relapse-frequency definitions follow standard pediatric nephrology consensus (ISKDC-derived) categories: infrequent, frequent, and steroid-dependent relapsers."}


class VURGradingCalculator(Calculator):
    key = "vur_grading"

    def compute(self, a: dict) -> dict:
        if not a.get("refluxExtent") or not a.get("dilation"):
            return {"headline": "Select reflux extent and dilation.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if a.get("papillaryImpressionsLost") == "yes" or a.get("dilation") == "gross":
            grade = "V"
        elif a.get("dilation") == "moderate" and a.get("tortuosity") == "yes":
            grade = "IV"
        elif a.get("dilation") in ("mild", "moderate"):
            grade = "III"
        elif a.get("refluxExtent") == "pelvis-and-calyces":
            grade = "II"
        else:
            grade = "I"
        flags = []
        if grade in ("IV", "V"):
            flags.append({"text": "Higher-grade reflux carries greater risk of renal scarring - surgical correction (ureteral reimplantation or endoscopic injection) is more often considered, alongside continued antibiotic prophylaxis discussion.", "severity": "warning"})
        else:
            flags.append({"text": "Lower-grade reflux (I-III) often resolves spontaneously with growth - observation with or without prophylactic antibiotics is a common approach.", "severity": "caution"})
        return {
            "headline": f"Grade {grade}", "headlineSeverity": "warning" if grade in ("IV", "V") else "caution",
            "metrics": [], "flags": flags,
            "notes": "Based on the International Reflux Study grading system (I-V) from voiding cystourethrogram (VCUG) findings. Management (observation vs. prophylaxis vs. surgical correction) depends on grade, breakthrough UTIs, and renal scarring on other imaging (e.g., DMSA scan), not grade alone.",
        }


class HydronephrosisGradingPediatricCalculator(Calculator):
    key = "hydronephrosis_grading_pediatric"

    def compute(self, a: dict) -> dict:
        if a.get("parenchymalThinning") == "significant":
            grade = 4
        elif a.get("calycealInvolvement") == "all" and a.get("parenchymalThinning") == "mild":
            grade = 3
        elif a.get("calycealInvolvement") in ("all", "some"):
            grade = 2
        elif a.get("pelvisDilation") == "yes":
            grade = 1
        else:
            grade = 0
        flags = []
        if grade >= 3:
            flags.append({"text": "Higher-grade hydronephrosis warrants pediatric urology involvement and close follow-up imaging; consider VCUG/MAG3 renogram to evaluate for obstruction or reflux.", "severity": "warning"})
        elif grade >= 1:
            flags.append({"text": "Lower-grade hydronephrosis is often followed with serial ultrasound; escalate imaging if it progresses or symptoms develop.", "severity": "caution"})
        return {
            "headline": f"Grade {grade}", "headlineSeverity": "warning" if grade >= 3 else ("caution" if grade >= 1 else "good"),
            "metrics": [{"label": "Grade", "value": grade}], "flags": flags,
            "notes": "A simplified version of SFU-style hydronephrosis grading. Current practice increasingly uses the more detailed UTD (Urinary Tract Dilation) classification, which also incorporates ureteral and bladder findings - use the formal radiology grading for management decisions.",
        }


class PediatricHTNScreeningCalculator(Calculator):
    key = "pediatric_htn_screening"

    def compute(self, a: dict) -> dict:
        age, sbp, dbp = _num_or_none(a.get("age")), _num_or_none(a.get("sbp")), _num_or_none(a.get("dbp"))
        if age is None or sbp is None or dbp is None:
            return {"headline": "Enter age, SBP, and DBP.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        if age < 13:
            return {
                "headline": "Full percentile evaluation needed", "headlineSeverity": "caution", "metrics": [],
                "flags": [{"text": "For children under 13, BP must be compared against age/sex/height-specific percentile charts (AAP 2017) - a single cutoff cannot substitute for that lookup. Use a pediatric BP percentile calculator with height entered.", "severity": "caution"}],
                "notes": "This tool only screens using adult-aligned thresholds for ages 13 and older, per AAP 2017 guidance that adolescents use adult-equivalent cutoffs. Deliberately does not assert an under-13 percentile cutoff without height-based normative data.",
            }
        if sbp >= 140 or dbp >= 90:
            tier, sev = "Stage 2 hypertension", "critical"
        elif sbp >= 130 or dbp >= 80:
            tier, sev = "Stage 1 hypertension", "warning"
        elif sbp >= 120:
            tier, sev = "Elevated blood pressure", "caution"
        else:
            tier, sev = "Normal", "good"
        return {
            "headline": tier, "headlineSeverity": sev, "metrics": [{"label": "BP", "value": f"{sbp:g}/{dbp:g}", "unit": "mmHg"}], "flags": [],
            "notes": "Adolescents \u226513 use adult-equivalent BP thresholds per AAP 2017 guidance.",
        }


class PostUTIImagingDecisionCalculator(Calculator):
    key = "post_uti_imaging_decision"

    def compute(self, a: dict) -> dict:
        atypical = [x for x in _list(a.get("atypicalFeatures")) if x != "none"]
        recommend_ultrasound = a.get("febrileUti") == "yes" or len(atypical) > 0 or a.get("recurrentUti") == "yes"
        recommend_further_imaging = len(atypical) > 0 or a.get("recurrentUti") == "yes"
        flags = []
        if recommend_ultrasound:
            flags.append({"text": "Renal and bladder ultrasound is reasonable - recommended after a first febrile UTI in most guideline approaches, and especially with atypical features or recurrence.", "severity": "caution"})
        if recommend_further_imaging:
            flags.append({"text": "Atypical features and/or recurrent UTI raise the case for further imaging (VCUG or MAG3 renogram) beyond ultrasound alone - discuss with pediatric urology/nephrology.", "severity": "warning"})
        return {
            "headline": "Imaging workup indicated" if recommend_ultrasound else "Imaging not strongly indicated from entries",
            "headlineSeverity": "warning" if recommend_further_imaging else ("caution" if recommend_ultrasound else "good"),
            "metrics": [], "flags": flags,
            "notes": "Reflects the general logic behind post-UTI imaging pathways (ultrasound for febrile/recurrent/atypical presentations; further imaging reserved for atypical or recurrent cases) - exact criteria and imaging modality choice vary between guideline bodies (AAP vs. NICE vs. local protocol).",
        }


class PediatricCKDGrowthNutritionCalculator(Calculator):
    key = "pediatric_ckd_growth_nutrition"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        if a.get("heightPercentileTrend") == "declining":
            flags.append({"text": "Declining height percentile in pediatric CKD warrants formal growth assessment and consideration of growth hormone therapy if growth failure persists despite optimized nutrition and metabolic control.", "severity": "warning"})
            sev = "warning"
        if a.get("dietaryIntakeAdequate") == "no":
            flags.append({"text": "Inadequate intake - involve a pediatric renal dietitian; caloric and protein needs differ from adult CKD guidance and must support growth.", "severity": "warning"})
            sev = "warning"
        if a.get("ckdStage") == "severe" and a.get("onGrowthHormone") != "yes" and a.get("heightPercentileTrend") == "declining":
            flags.append({"text": "Growth hormone therapy is an established option for growth failure in pediatric CKD once nutrition and metabolic bone disease are addressed.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"{len(flags)} item(s) flagged" if flags else "No growth/nutrition concerns flagged from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Pediatric CKD nutrition/growth management differs substantially from adult CKD - growth is a primary treatment goal in its own right. This checklist is a screening prompt, not a nutrition prescription; involve a pediatric renal dietitian.",
        }


class PediatricHUSSeverityCalculator(Calculator):
    key = "pediatric_hus_severity"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "caution"
        if a.get("antibioticsGiven") == "yes":
            flags.append({"text": "Antibiotics for suspected STEC infection are generally avoided - some data suggest they may increase HUS risk by promoting toxin release; worth revisiting with the treating team if not yet stopped.", "severity": "warning"})
        if a.get("neurologicSymptoms") == "yes":
            flags.append({"text": "Neurologic involvement indicates severe disease - consider PICU-level monitoring; complement inhibitor therapy has been used in severe/neurologic STEC-HUS at some centers despite being primarily studied in atypical HUS.", "severity": "critical"})
            sev = "critical"
        if a.get("anuriaOrOliguria") == "yes":
            flags.append({"text": "Oliguria/anuria - monitor closely for need for renal replacement therapy; fluid management should avoid both volume overload and dehydration.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        flags.append({"text": "Avoid antimotility agents; supportive care (careful fluid/electrolyte management, individualized transfusion thresholds) is the mainstay for typical STEC-HUS.", "severity": "caution"})
        return {
            "headline": "Severe features present" if sev == "critical" else "Supportive care with close monitoring",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "STEC-HUS (Shiga-toxin-producing E. coli hemolytic uremic syndrome) is predominantly a pediatric disease; most cases are self-limited with supportive care, but severe/neurologic cases need escalated monitoring. See also the aHUS vs. TTP Differentiation module if the trigger is unclear.",
        }


class BiopsyBleedingRiskCalculator(Calculator):
    key = "biopsy_bleeding_risk"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        plt, inr = _num_or_none(a.get("platelets")), _num_or_none(a.get("inr"))
        if plt is not None and plt < 100:
            flags.append({"text": "Platelet count <100k - many protocols recommend correction before proceeding.", "severity": "warning"})
            sev = "warning"
        if inr is not None and inr > 1.5:
            flags.append({"text": "INR >1.5 - correct coagulopathy before biopsy per most protocols.", "severity": "warning"})
            sev = "warning"
        if a.get("onAnticoagulation") == "yes":
            flags.append({"text": "On anticoagulation/antiplatelet therapy - confirm the appropriate hold interval for the specific agent before proceeding.", "severity": "warning"})
            sev = "warning"
        if a.get("bpControlled") == "no":
            flags.append({"text": "Uncontrolled BP - treat before biopsy; hypertension increases bleeding risk.", "severity": "warning"})
            sev = "warning"
        if a.get("singleKidney") == "yes":
            flags.append({"text": "Single functioning kidney - a bleeding complication carries higher stakes; weigh risk/benefit carefully.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if a.get("activeUTI") == "yes":
            flags.append({"text": "Active untreated infection - treat first to reduce risk of seeding or complication.", "severity": "warning"})
            sev = "warning"
        return {
            "headline": f"{len(flags)} bleeding-risk factor(s) identified" if flags else "No major bleeding-risk factors flagged",
            "headlineSeverity": sev,
            "metrics": [{"label": "Platelets", "value": plt if plt is not None else "\u2014", "unit": "\u00d710\u00b3/\u00b5L"}, {"label": "INR", "value": inr if inr is not None else "\u2014"}], "flags": flags,
            "notes": "Reflects commonly cited pre-biopsy safety checks; exact platelet/INR thresholds and anticoagulation hold times vary by institutional protocol and agent - confirm locally.",
        }


class FistulaMaturationCalculator(Calculator):
    key = "fistula_maturation"

    def compute(self, a: dict) -> dict:
        weeks, diam, depth, flow = (_num_or_none(a.get(k)) for k in ["weeksSinceCreation", "diameterMm", "depthMm", "flowMlMin"])
        criteria = []
        if weeks is not None:
            criteria.append({"label": "\u22656 weeks since creation", "met": weeks >= 6})
        if diam is not None:
            criteria.append({"label": "Diameter \u22656 mm", "met": diam >= 6})
        if depth is not None:
            criteria.append({"label": "Depth \u22646 mm from skin", "met": depth <= 6})
        if flow is not None:
            criteria.append({"label": "Flow \u2265600 mL/min", "met": flow >= 600})
        if not criteria:
            return {"headline": "Enter at least one measurement.", "headlineSeverity": "caution", "metrics": [], "flags": [], "notes": ""}
        all_met = all(c["met"] for c in criteria)
        flags = [{"text": f"Not yet meeting: {c['label']}.", "severity": "caution"} for c in criteria if not c["met"]]
        return {
            "headline": "Meets \"Rule of 6s\" maturation criteria" if all_met else "Not yet mature by Rule of 6s",
            "headlineSeverity": "good" if all_met else "caution",
            "metrics": [{"label": c["label"], "value": "\u2713" if c["met"] else "\u2717"} for c in criteria], "flags": flags,
            "notes": "The \"Rule of 6s\" (\u22656 weeks, \u22656mm diameter, \u22646mm depth, \u2265600 mL/min flow) is a commonly used bedside heuristic for fistula readiness to cannulate - formal ultrasound mapping or a cannulation trial remains the definitive step.",
        }


class GadoliniumNSFRiskCalculator(Calculator):
    key = "gadolinium_nsf_risk"

    def compute(self, a: dict) -> dict:
        egfr = _num_or_none(a.get("egfr"))
        flags = []
        sev = "good"
        if a.get("onDialysis") == "yes" or (egfr is not None and egfr < 15):
            flags.append({"text": "eGFR <15 or on dialysis - highest-risk group for nephrogenic systemic fibrosis; avoid higher-risk (linear) agents, prefer a macrocyclic agent if contrast is truly necessary, and consider prompt dialysis after administration if already on HD.", "severity": "critical"})
            sev = "critical"
        elif egfr is not None and egfr < 30:
            flags.append({"text": "eGFR 15-29 - increased NSF risk; use the lowest-risk (macrocyclic) agent at the lowest diagnostic dose if gadolinium is necessary.", "severity": "warning"})
            sev = "warning"
        elif egfr is not None and egfr < 60:
            flags.append({"text": "eGFR 30-59 - modestly increased risk; macrocyclic agents remain preferred practice at many institutions.", "severity": "caution"})
            sev = "caution"
        if a.get("acuteKidneyInjury") == "yes":
            flags.append({"text": "Active AKI - risk may be higher than eGFR alone suggests since renal function is unstable; reassess before administration.", "severity": "warning"})
            if sev in ("good", "caution"):
                sev = "warning"
        if a.get("priorNsfHistory") == "yes":
            flags.append({"text": "Prior NSF history - avoid gadolinium-based contrast entirely if at all possible.", "severity": "critical"})
            sev = "critical"
        if a.get("agentClass") == "group1-high-risk":
            flags.append({"text": "Higher-risk (linear) agent selected - consider switching to a macrocyclic (group II) agent, which carries substantially lower reported NSF risk.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        return {
            "headline": "High NSF risk - reconsider gadolinium use" if sev == "critical" else ("Increased NSF risk - use precautions" if sev == "warning" else "Low NSF risk from entries"),
            "headlineSeverity": sev,
            "metrics": [{"label": "eGFR", "value": egfr, "unit": "mL/min/1.73m\u00b2"}] if egfr is not None else [], "flags": flags,
            "notes": "NSF risk is concentrated in eGFR <30 (especially <15/dialysis) and is substantially lower with modern macrocyclic (group II) agents than older linear (group I) agents. Follow your institution's contrast/MRI safety protocol.",
        }


class CatheterExitSiteInfectionCalculator(Calculator):
    key = "catheter_exit_site_infection"

    def compute(self, a: dict) -> dict:
        signs = sum(1 for k in ["erythema", "purulentDrainage", "tenderness"] if a.get(k) == "yes")
        if a.get("tunnelInvolvement") == "yes":
            classification, sev = "Tunnel infection", "critical"
        elif a.get("purulentDrainage") == "yes" or signs >= 2:
            classification, sev = "Exit-site infection", "warning"
        elif signs == 1:
            classification, sev = "Possible early exit-site infection - monitor closely", "caution"
        else:
            classification, sev = "No signs of exit-site infection", "good"
        flags = []
        if sev == "critical":
            flags.append({"text": "Tunnel infection often requires catheter removal in addition to antibiotics - involve the access/surgical team promptly.", "severity": "critical"})
        elif sev == "warning":
            flags.append({"text": "Start empiric antibiotics per local protocol (typically covering Staph, including MRSA) and send a wound culture.", "severity": "warning"})
        if a.get("feverOrSystemic") == "yes":
            flags.append({"text": "Systemic symptoms present - evaluate for bacteremia/peritonitis (if PD) or catheter-related bloodstream infection (if HD catheter) rather than a localized exit-site process alone.", "severity": "critical"})
        return {
            "headline": classification, "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Based on standard ISPD/KDOQI exit-site and tunnel infection definitions for dialysis catheters. Culture results and clinical trajectory should guide antibiotic choice and duration.",
        }


class DrugNephrotoxicityChecklistCalculator(Calculator):
    key = "drug_nephrotoxicity_checklist"

    def compute(self, a: dict) -> dict:
        exp = [e for e in _list(a.get("exposures")) if e != "none"]
        has = lambda k: k in exp
        flags = []
        sev = "good"
        if has("nsaid") and has("aceiArb") and has("diuretic"):
            flags.append({"text": "\"Triple whammy\" combination (NSAID + ACEi/ARB + diuretic) present - substantially raises AKI risk; consider discontinuing one agent, especially the NSAID.", "severity": "critical"})
            sev = "critical"
        if has("aminoglycoside"):
            flags.append({"text": "Aminoglycoside - monitor trough levels and renal function closely; consider once-daily dosing and duration limits.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        if has("amphotericin"):
            flags.append({"text": "Amphotericin B - significant nephrotoxicity risk; consider a liposomal formulation and monitor electrolytes (especially potassium/magnesium) and renal function.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        if has("cisplatinOrPlatinum"):
            flags.append({"text": "Platinum-based chemotherapy - ensure adequate hydration and consider dose adjustment for renal function.", "severity": "warning"})
            if sev != "critical":
                sev = "warning"
        if has("vancomycin"):
            flags.append({"text": "Vancomycin - monitor levels (AUC-guided dosing where available) and renal function.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if has("ivContrast"):
            flags.append({"text": "Recent/planned IV contrast - see the Contrast-Induced Nephropathy Risk module for a fuller estimate.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if has("calcineurinInhibitor"):
            flags.append({"text": "Calcineurin inhibitor (e.g., tacrolimus/cyclosporine) - nephrotoxic at supratherapeutic levels; check trough.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        if has("lithium"):
            flags.append({"text": "Lithium - check level and renal function; chronic use is associated with CKD and nephrogenic diabetes insipidus.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": f"{len(exp)} nephrotoxic exposure(s) identified" if exp else "No nephrotoxic exposures selected",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "A checklist of commonly cited nephrotoxic exposures and combinations, not an exhaustive drug-interaction database. Always cross-check against a full medication reconciliation and current renal dosing references.",
        }


class RenalDoseAdjustmentTriageCalculator(Calculator):
    key = "renal_dose_adjustment_triage"

    LABELS = {
        "antibiotics-renally-cleared": "Renally-cleared antibiotics (beta-lactams, vancomycin, aminoglycosides)",
        "doacs": "Direct oral anticoagulants",
        "opioids": "Opioids",
        "antiepileptics-renally-cleared": "Renally-cleared antiepileptics (gabapentin, pregabalin, levetiracetam)",
        "metforminOrOtherDiabetesMeds": "Diabetes medications",
        "digoxin": "Digoxin",
        "lmwh": "Low molecular weight heparin",
    }

    def compute(self, a: dict) -> dict:
        egfr = _num_or_none(a.get("egfr"))
        classes = [c for c in _list(a.get("drugClasses")) if c != "none"]
        flags = []
        if egfr is not None and egfr < 60 and classes:
            for c in classes:
                label = self.LABELS.get(c, c)
                flags.append({"text": f"{label} commonly needs dose or interval adjustment below eGFR 60 - verify the specific drug and exact adjustment against a current renal dosing reference (e.g. Lexicomp, Micromedex) or pharmacist consult; do not rely on a general rule for the precise number.", "severity": "warning" if egfr < 30 else "caution"})
        return {
            "headline": f"{len(flags)} drug class(es) flagged for dosing review" if flags else "No flagged classes from entries",
            "headlineSeverity": "warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good"),
            "metrics": [{"label": "eGFR", "value": egfr, "unit": "mL/min/1.73m\u00b2"}] if egfr is not None else [], "flags": flags,
            "notes": "This is a triage/reminder tool, not a dosing calculator - it flags which medication classes commonly require renal adjustment at this eGFR so nothing gets missed, but the exact dose or interval must come from a verified drug-specific reference. Fabricating a specific number here would carry real risk of harm if wrong.",
        }


class PerioperativeMedHoldChecklistCalculator(Calculator):
    key = "perioperative_med_hold_checklist"

    def compute(self, a: dict) -> dict:
        meds = [m for m in _list(a.get("currentMeds")) if m != "none"]
        flags = []
        if "sglt2i" in meds:
            flags.append({"text": "Hold SGLT2 inhibitors for at least 3 days before elective surgery (longer for some agents) - euglycemic diabetic ketoacidosis risk in the perioperative period.", "severity": "warning"})
        if "aceiArb" in meds and a.get("procedureType") == "major-surgery":
            flags.append({"text": "Many anesthesia protocols hold ACEi/ARB the morning of major surgery due to intraoperative hypotension risk - confirm against local protocol.", "severity": "caution"})
        if "metformin" in meds and a.get("procedureType") == "contrast-procedure":
            flags.append({"text": "Hold metformin at the time of iodinated contrast administration in patients with reduced eGFR, and resume only after confirming stable renal function.", "severity": "caution"})
        if "doacsOrWarfarin" in meds:
            flags.append({"text": "Anticoagulant hold timing depends on the specific agent, renal function, and bleeding risk of the procedure - confirm against a bridging/hold protocol rather than a blanket rule.", "severity": "warning"})
        if "diuretics" in meds and a.get("procedureType") != "minor":
            flags.append({"text": "Consider holding diuretics on the morning of surgery if volume depletion/hypotension risk is a concern - balance against volume-overload risk.", "severity": "caution"})
        if "nsaid" in meds:
            flags.append({"text": "NSAIDs are often held before procedures with bleeding risk and in patients with reduced eGFR - confirm timing against local protocol.", "severity": "caution"})
        return {
            "headline": f"{len(flags)} medication(s) with hold guidance" if flags else "No flagged medications for this procedure type",
            "headlineSeverity": "warning" if any(f["severity"] == "warning" for f in flags) else ("caution" if flags else "good"),
            "metrics": [], "flags": flags,
            "notes": "General perioperative hold patterns for common nephrology-relevant medications - exact hold duration and resumption timing vary by agent, procedure, and institutional protocol. This is a reminder checklist, not an anesthesia protocol.",
        }


class PreeclampsiaCriteriaCalculator(Calculator):
    key = "preeclampsia_criteria"

    def compute(self, a: dict) -> dict:
        high_rf = [x for x in _list(a.get("highRiskFactors")) if x != "none"]
        mod_rf = [x for x in _list(a.get("moderateRiskFactors")) if x != "none"]
        aspirin_indicated = len(high_rf) >= 1 or len(mod_rf) >= 2
        flags = []
        if aspirin_indicated:
            flags.append({"text": "Meets a commonly used risk-factor threshold for low-dose aspirin prophylaxis (81-162mg daily, typically started 12-28 weeks) per ACOG/USPSTF risk-based approach.", "severity": "caution"})
        ga, sbp, dbp = _num_or_none(a.get("gestationalAgeWeeks")), _num_or_none(a.get("sbp")), _num_or_none(a.get("dbp"))
        htn_present = (sbp is not None and sbp >= 140) or (dbp is not None and dbp >= 90)
        severe = [x for x in _list(a.get("severeFeatures")) if x != "none"]
        meets_diagnosis = ga is not None and ga >= 20 and htn_present and (a.get("proteinuria") == "yes" or len(severe) > 0)
        if meets_diagnosis and len(severe) > 0:
            headline, sev = "Preeclampsia with severe features", "critical"
            flags.append({"text": "Severe features present - this typically prompts a delivery-timing discussion regardless of gestational age, with magnesium sulfate for seizure prophylaxis and antihypertensive therapy for severe-range BP.", "severity": "critical"})
        elif meets_diagnosis:
            headline, sev = "Meets preeclampsia diagnostic criteria", "warning"
            flags.append({"text": "Close maternal/fetal monitoring, antihypertensive therapy as indicated, and delivery-timing discussion based on gestational age and severity trajectory.", "severity": "warning"})
        elif htn_present and ga is not None and ga >= 20:
            headline, sev = "Gestational hypertension without proteinuria/severe features - continue monitoring", "caution"
        else:
            headline, sev = "Criteria not met from entries", "good"
        return {
            "headline": headline, "headlineSeverity": sev,
            "metrics": [{"label": "Aspirin prophylaxis", "value": "Indicated" if aspirin_indicated else "Not indicated from entries"}], "flags": flags,
            "notes": "Based on ACOG diagnostic criteria for preeclampsia (new hypertension \u226520 weeks plus proteinuria or severe features) and the risk-factor-based approach to aspirin prophylaxis. Distinguishing preeclampsia from a lupus flare can be difficult - see the companion \"Preeclampsia vs. Lupus Flare\" module when relevant.",
        }


class CKDPregnancyRiskCalculator(Calculator):
    key = "ckd_pregnancy_risk"

    def compute(self, a: dict) -> dict:
        if a.get("ckdStage") == "dialysis" or a.get("ckdStage") == "G4-G5" or a.get("systemicDiseaseActive") == "yes" or a.get("proteinuriaPrePregnancy") == "nephrotic-range":
            risk_level, sev = "Very high risk", "critical"
        elif a.get("ckdStage") == "G3a-G3b" or (a.get("hypertensionPrePregnancy") == "yes" and a.get("proteinuriaPrePregnancy") != "none"):
            risk_level, sev = "High risk", "warning"
        elif a.get("hypertensionPrePregnancy") == "yes" or a.get("proteinuriaPrePregnancy") == "mild":
            risk_level, sev = "Moderate risk", "caution"
        else:
            risk_level, sev = "Low risk", "good"
        flags = []
        if sev == "critical":
            flags.append({"text": "Very high risk - maternal-fetal medicine and nephrology co-management from preconception/early pregnancy is essential; discuss risk of maternal CKD progression, preeclampsia, and preterm delivery explicitly.", "severity": "critical"})
        elif sev == "warning":
            flags.append({"text": "High risk - close joint monitoring (BP, proteinuria trend, fetal growth) at increased frequency is warranted.", "severity": "warning"})
        elif sev == "caution":
            flags.append({"text": "Moderate risk - routine joint monitoring with lower threshold for escalation if BP or proteinuria worsen.", "severity": "caution"})
        return {
            "headline": risk_level, "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Inspired by the Piccoli et al. CKD-in-pregnancy risk classification concept (stage, hypertension, proteinuria, and systemic disease activity as key drivers of risk), presented here in simplified form. Individualized maternal-fetal medicine and nephrology co-management is essential regardless of risk tier.",
        }


class PreeclampsiaVsLupusFlareCalculator(Calculator):
    key = "preeclampsia_vs_lupus_flare"

    def compute(self, a: dict) -> dict:
        lupus_pts, preeclampsia_pts = 0, 0
        if a.get("complementLevels") == "low":
            lupus_pts += 2
        if a.get("antiDsdnaTrend") == "rising":
            lupus_pts += 2
        if a.get("urineSedimentActive") == "yes":
            lupus_pts += 2
        if a.get("extrarenalLupusActivity") == "yes":
            lupus_pts += 1
        if a.get("onsetTiming") == "early-pregnancy-less20wk":
            lupus_pts += 1
        if a.get("responseToSteroidsTrial") == "improved":
            lupus_pts += 1
        if a.get("onsetTiming") == "later-pregnancy":
            preeclampsia_pts += 1
        if a.get("complementLevels") == "normal" and a.get("antiDsdnaTrend") == "stable" and a.get("urineSedimentActive") == "no":
            preeclampsia_pts += 2
        if lupus_pts > preeclampsia_pts:
            favors = "lupus nephritis flare"
        elif preeclampsia_pts > lupus_pts:
            favors = "preeclampsia"
        else:
            favors = "unclear \u2014 features overlap"
        flags = []
        if favors == "lupus nephritis flare":
            flags.append({"text": "Consider escalating immunosuppression rather than treating as preeclampsia - delivery alone will not address an active lupus flare.", "severity": "warning"})
        elif favors == "preeclampsia":
            flags.append({"text": "Delivery remains the definitive treatment for preeclampsia - escalating immunosuppression would not address it and carries its own risk.", "severity": "warning"})
        else:
            flags.append({"text": "Overlap is common and well recognized - many centers manage empirically for both while awaiting clarifying labs, given the differing treatment implications.", "severity": "caution"})
        return {
            "headline": f"Pattern favors: {favors}", "headlineSeverity": "warning", "metrics": [], "flags": flags,
            "notes": "Complement consumption, rising anti-dsDNA, and an active urine sediment favor a lupus flare; normal complement, stable serology, and a bland sediment favor preeclampsia - but overlap is well recognized and this is a structured aid, not a validated diagnostic algorithm.",
        }


class NephrologyPregnancyMedSafetyCalculator(Calculator):
    key = "nephrology_pregnancy_med_safety"

    NOTES = {
        "aceiArb": "ACEi/ARB - contraindicated in pregnancy (fetotoxic, especially 2nd/3rd trimester); switch to labetalol, nifedipine, or methyldopa before conception if possible.",
        "mycophenolate": "Mycophenolate - teratogenic; must be switched (commonly to azathioprine) at least 6 weeks before attempting conception.",
        "cyclophosphamide": "Cyclophosphamide - teratogenic; avoid in pregnancy except in life-threatening maternal disease with no alternative.",
        "methotrexate": "Methotrexate - teratogenic; must be discontinued at least 1-3 months before conception.",
        "nsaid": "NSAIDs - avoid, especially after 20 weeks (fetal renal effects) and in the third trimester (premature ductus closure).",
        "warfarin": "Warfarin - teratogenic (especially 1st trimester); typically switched to heparin/LMWH for pregnancy if anticoagulation is needed.",
        "sglt2i": "SGLT2 inhibitors - insufficient safety data in pregnancy; generally discontinued once pregnancy is identified or planned.",
        "statin": "Statins - generally avoided in pregnancy per longstanding practice, though evidence of harm is less robust than once believed; discuss with obstetrics.",
    }

    def compute(self, a: dict) -> dict:
        meds = [m for m in _list(a.get("currentMeds")) if m != "none"]
        flags = [{"text": self.NOTES[m], "severity": "caution" if m == "statin" else "critical"} for m in meds if m in self.NOTES]
        return {
            "headline": f"{len(flags)} medication(s) need pregnancy-safety review" if flags else "No flagged medications from entries",
            "headlineSeverity": "critical" if any(f["severity"] == "critical" for f in flags) else ("caution" if flags else "good"),
            "metrics": [], "flags": flags,
            "notes": "This covers a short list of well-established, high-impact teratogens common in nephrology practice - it is not a comprehensive pregnancy drug-safety database. Confirm any medication change against a verified teratogenicity reference (e.g., Reprotox, MotherToBaby) and obstetric/maternal-fetal medicine input before stopping or switching anything.",
        }


class HELLPCriteriaCalculator(Calculator):
    key = "hellp_criteria"

    def compute(self, a: dict) -> dict:
        ast, alt, plt = _num_or_none(a.get("ast")), _num_or_none(a.get("alt")), _num_or_none(a.get("plateletCount"))
        elevated_liver = (ast is not None and ast >= 70) or (alt is not None and alt >= 70)
        low_plt = plt is not None and plt < 100
        meets = a.get("hemolysisEvidence") == "yes" and elevated_liver and low_plt
        flags = []
        if meets:
            flags.append({"text": "Meets classic HELLP criteria - this is an obstetric emergency; delivery is generally the definitive treatment once the maternal condition is unstable or the pregnancy is at/near term.", "severity": "critical"})
        sev = "critical" if meets else (("warning") if (elevated_liver or low_plt or a.get("hemolysisEvidence") == "yes") else "good")
        return {
            "headline": "Meets HELLP syndrome criteria" if meets else "Does not meet all three HELLP criteria",
            "headlineSeverity": sev,
            "metrics": [{"label": "AST", "value": ast if ast is not None else "\u2014", "unit": "U/L"}, {"label": "ALT", "value": alt if alt is not None else "\u2014", "unit": "U/L"}, {"label": "Platelets", "value": plt if plt is not None else "\u2014", "unit": "\u00d710\u2079/L"}], "flags": flags,
            "notes": "HELLP (Hemolysis, Elevated Liver enzymes, Low Platelets) is considered a severe variant of preeclampsia. Exact laboratory cutoffs vary slightly by reference (commonly AST/ALT \u226570 U/L and platelets <100,000/\u00b5L) - confirm against your institution's reference ranges.",
        }


class ConservativeKidneyManagementSuitabilityCalculator(Calculator):
    key = "conservative_kidney_management_suitability"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        try:
            cfs = int(a.get("cfsLevel") or "0")
        except (TypeError, ValueError):
            cfs = 0
        if cfs >= 7 or a.get("comorbidityBurden") == "high":
            flags.append({"text": "High frailty/comorbidity burden - literature suggests dialysis may not offer a clear survival advantage over conservative management in this population; a structured conservative-care discussion is appropriate regardless of eventual choice.", "severity": "warning"})
            sev = "warning"
        if a.get("patientPreference") == "prefers-conservative":
            flags.append({"text": "Patient preference for conservative management should be honored with a structured plan (symptom management, advance care planning) - see the companion Symptom Management and Advance Care Planning modules.", "severity": "caution"})
        if a.get("patientPreference") == "undecided":
            flags.append({"text": "Consider a formal shared decision-making conversation, ideally with a decision aid comparing dialysis and conservative-management trajectories.", "severity": "caution"})
        return {
            "headline": f"{len(flags)} item(s) to factor into the discussion" if flags else "No strong signal either way from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "Conservative (non-dialysis) kidney management is a legitimate care pathway, not \"no care\" - it includes active symptom management, and outcomes for appropriately selected patients (especially elderly/frail with high comorbidity) can be comparable in quality of remaining life. This tool structures the discussion; it does not make the decision.",
        }


class DialysisPrognosisSurpriseQuestionCalculator(Calculator):
    key = "dialysis_prognosis_surprise_question"

    def compute(self, a: dict) -> dict:
        flags = []
        sev = "good"
        if a.get("surpriseQuestion") == "no":
            flags.append({"text": "A \"no\" answer to the surprise question is a validated simple flag for elevated 12-month mortality risk in dialysis populations - consider a palliative care referral and advance care planning conversation.", "severity": "warning"})
            sev = "warning"
        hosp = _num_or_none(a.get("hospitalizationsPast6mo"))
        if hosp is not None and hosp >= 2:
            flags.append({"text": "Multiple hospitalizations in the past 6 months is an additional marker of high symptom/mortality burden.", "severity": "warning"})
            sev = "warning"
        if a.get("functionalStatusDeclining") == "yes":
            flags.append({"text": "Declining functional status alongside other markers strengthens the case for a goals-of-care conversation.", "severity": "caution"})
            if sev == "good":
                sev = "caution"
        return {
            "headline": "Elevated mortality-risk signal" if sev == "warning" else "No strong mortality-risk signal from entries",
            "headlineSeverity": sev, "metrics": [], "flags": flags,
            "notes": "The \"surprise question\" is a simple, validated prognostic screening tool used in nephrology and palliative care research - a \"no\" response correlates with substantially higher mortality risk. It is a screening prompt for further prognostic discussion, not a prognosis itself.",
        }


class UremicSymptomManagementCalculator(Calculator):
    key = "uremic_symptom_management"

    TIPS = {
        "pruritus": "Pruritus: consider gabapentin/pregabalin (renally dosed), emollients, and address hyperphosphatemia if present; antihistamines alone are often ineffective for uremic pruritus.",
        "restlessLegs": "Restless legs: correct iron deficiency first; gabapentinoids are commonly used renally-adjusted options.",
        "nauseaAppetiteLoss": "Nausea/appetite loss: consider antiemetics (many are renally cleared, adjust dosing) and address contributing metabolic derangements (uremia itself, constipation).",
        "pain": "Pain: many opioids accumulate active/toxic metabolites in kidney failure - fentanyl, hydromorphone, and methadone are generally preferred over morphine or codeine.",
        "dyspnea": "Dyspnea: evaluate for treatable causes (volume overload, anemia) but do not withhold symptomatic management (e.g., opioids for refractory dyspnea) pending workup in advanced disease.",
        "fatigue": "Fatigue is often multifactorial (anemia, poor sleep, depression, uremia itself) - evaluate for correctable contributors before attributing solely to CKD.",
        "insomnia": "Insomnia: address restless legs and pruritus if present, as they often disrupt sleep; be cautious with renally-cleared sedative-hypnotics.",
    }

    def compute(self, a: dict) -> dict:
        sym = [s for s in _list(a.get("symptoms")) if s != "none"]
        flags = [{"text": self.TIPS[s], "severity": "caution"} for s in sym if s in self.TIPS]
        return {
            "headline": f"{len(sym)} symptom(s) addressed" if sym else "No symptoms selected",
            "headlineSeverity": "caution" if sym else "good", "metrics": [], "flags": flags,
            "notes": "Symptom management principles differ meaningfully from standard practice because of altered drug clearance in kidney failure - dose and agent selection matter as much as the decision to treat. This is general guidance; involve palliative care for refractory symptoms.",
        }


class DialysisWithdrawalPlanningCalculator(Calculator):
    key = "dialysis_withdrawal_planning"

    LABELS = {
        "prognosisDiscussed": "Prognosis discussion", "symptomManagementPlanInPlace": "Symptom management plan",
        "hospiceReferralMade": "Hospice referral", "familyPsychosocialSupport": "Family/psychosocial support",
        "advanceDirectiveDocumented": "Advance directive", "expectedTimeToDeathDiscussed": "Expected time-course discussion",
    }

    def compute(self, a: dict) -> dict:
        keys = list(self.LABELS.keys())
        outstanding = [k for k in keys if a.get(k) != "yes"]
        flags = [{"text": f"{self.LABELS[k]} not yet confirmed.", "severity": "caution"} for k in outstanding]
        return {
            "headline": "All standard withdrawal-planning items addressed" if not outstanding else f"{len(outstanding)} item(s) outstanding",
            "headlineSeverity": "good" if not outstanding else ("warning" if len(outstanding) >= 3 else "caution"),
            "metrics": [{"label": "Items complete", "value": f"{len(keys) - len(outstanding)} / {len(keys)}"}], "flags": flags,
            "notes": "A checklist for the dialysis-withdrawal conversation and its aftermath - most patients die within days to two weeks after withdrawal depending on residual kidney function, and proactive symptom/hospice planning meaningfully improves the experience for patient and family.",
        }


class AdvanceCareplanningCKDCalculator(Calculator):
    key = "advance_care_planning_ckd"

    LABELS = {
        "healthcareProxyIdentified": "Healthcare proxy", "advanceDirectiveCompleted": "Advance directive",
        "dialysisPreferencesDocumented": "Dialysis preferences", "goalsOfCareDiscussed": "Goals-of-care discussion", "polstDocumented": "POLST/MOLST",
    }

    def compute(self, a: dict) -> dict:
        keys = list(self.LABELS.keys())
        outstanding = [k for k in keys if a.get(k) != "yes"]
        flags = [{"text": f"{self.LABELS[k]} not yet confirmed complete.", "severity": "caution"} for k in outstanding]
        pct = round(((len(keys) - len(outstanding)) / len(keys)) * 100)
        return {
            "headline": "Advance care planning items complete" if not outstanding else f"{len(outstanding)} item(s) outstanding",
            "headlineSeverity": "good" if not outstanding else ("warning" if len(outstanding) >= 3 else "caution"),
            "metrics": [{"label": "Completion", "value": pct, "unit": "%"}], "flags": flags,
            "notes": "Advance care planning is relevant well before end-stage disease - ideally initiated at CKD G4 or at transplant/dialysis-planning stages rather than deferred to a crisis moment.",
        }
