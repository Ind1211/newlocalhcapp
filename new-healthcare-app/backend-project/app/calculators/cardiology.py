from app.calculators.base import Calculator


def _num_or_none(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class CHA2DS2VAScCalculator(Calculator):
    key = "cha2ds2vasc"

    def compute(self, a: dict) -> dict:
        age = _num_or_none(a.get("age"))
        if age is None or not a.get("sex"):
            return {
                "headline": "Enter age and sex to calculate.",
                "headlineSeverity": "caution",
                "metrics": [],
                "flags": [],
                "notes": "",
            }
        score = 0
        if a.get("chf") == "yes":
            score += 1
        if a.get("htn") == "yes":
            score += 1
        if age >= 75:
            score += 2
        elif age >= 65:
            score += 1
        if a.get("diabetes") == "yes":
            score += 1
        if a.get("stroke") == "yes":
            score += 2
        if a.get("vascular") == "yes":
            score += 1
        if a.get("sex") == "female":
            score += 1

        if score == 0:
            sev = "good"
            headline = f"CHA2DS2-VASc = {score} - low stroke risk."
        elif score == 1:
            sev = "caution"
            headline = f"CHA2DS2-VASc = {score} - low-moderate risk; anticoagulation may be considered."
        else:
            sev = "critical" if score >= 4 else ("warning" if score >= 2 else "caution")
            headline = f"CHA2DS2-VASc = {score} - anticoagulation typically recommended, pending bleeding-risk assessment."

        return {
            "headline": headline,
            "headlineSeverity": sev,
            "metrics": [{"label": "CHA2DS2-VASc score", "value": score, "unit": "/ 9"}],
            "flags": (
                [{"text": "Consider oral anticoagulation per guideline-directed therapy", "severity": sev}]
                if score >= 2
                else []
            ),
            "notes": "A validated score for guiding, not replacing, the anticoagulation decision; weigh alongside bleeding risk (e.g. HAS-BLED) and patient preference.",
        }


class HASBLEDCalculator(Calculator):
    key = "hasbled"
    FIELDS = ["htn", "renal", "liver", "stroke", "bleeding", "inr", "elderly", "drugs", "alcohol"]

    def compute(self, a: dict) -> dict:
        if any(not a.get(f) for f in self.FIELDS):
            return {
                "headline": "Answer all items to calculate.",
                "headlineSeverity": "caution",
                "metrics": [],
                "flags": [],
                "notes": "",
            }
        score = sum(1 for f in self.FIELDS if a.get(f) == "yes")
        sev = "warning" if score >= 3 else ("caution" if score >= 1 else "good")
        return {
            "headline": f"HAS-BLED = {score} - {'high' if score >= 3 else 'lower'} 1-year major bleeding risk on anticoagulation.",
            "headlineSeverity": sev,
            "metrics": [{"label": "HAS-BLED score", "value": score, "unit": "/ 9"}],
            "flags": (
                [{
                    "text": "High bleeding risk - does not automatically preclude anticoagulation, but flags need for closer monitoring and correction of modifiable risk factors",
                    "severity": "warning",
                }]
                if score >= 3
                else []
            ),
            "notes": "A high HAS-BLED score should prompt caution and monitoring, not automatic withholding of otherwise-indicated anticoagulation.",
        }


class MAPCalculator(Calculator):
    key = "map_calc"

    def compute(self, a: dict) -> dict:
        sbp, dbp = _num_or_none(a.get("sbp")), _num_or_none(a.get("dbp"))
        if sbp is None or dbp is None:
            return {
                "headline": "Enter systolic and diastolic BP to calculate.",
                "headlineSeverity": "caution",
                "metrics": [],
                "flags": [],
                "notes": "",
            }
        map_value = dbp + (sbp - dbp) / 3
        if map_value < 60:
            sev, headline = "critical", f"MAP approximately {map_value:.0f} mmHg - below the level generally considered needed for adequate organ perfusion."
        elif map_value < 70:
            sev, headline = "warning", f"MAP approximately {map_value:.0f} mmHg - borderline low."
        elif map_value <= 100:
            sev, headline = "good", f"MAP approximately {map_value:.0f} mmHg - within the commonly cited normal range."
        else:
            sev, headline = "caution", f"MAP approximately {map_value:.0f} mmHg - elevated."

        return {
            "headline": headline,
            "headlineSeverity": sev,
            "metrics": [{"label": "MAP", "value": round(map_value, 1), "unit": "mmHg"}],
            "flags": (
                [{"text": "MAP below approximately 60 mmHg is commonly cited as a threshold for inadequate organ perfusion - correlate clinically", "severity": "critical"}]
                if map_value < 60
                else []
            ),
            "notes": "Normal range shown (about 70-100 mmHg) is a commonly cited approximation, not a universal cutoff - clinical context matters more than the number alone.",
        }
