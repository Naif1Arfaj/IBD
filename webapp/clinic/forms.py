"""Patient entry form generated from the model's 10 input groups."""
import pandas as pd
from django import forms

from django.utils import timezone

from features import BINARY_01_COLS, BLANK_MEANS_NONE, FEATURES, GROUPS, OPTIONAL, OPTIONAL_BINARY_COLS, encode
from predict import _load as load_model
from rag.queries import label, unit

from .models import MonitoringPlan, TreatmentEvent
from .services import choices_for, dataset_stats

ENTRY_SECTIONS = [
    ("Patient profile", ["Demographic data"]),
    ("Signs and symptoms", ["Signs and symptoms"]),
    ("Clinical history", ["Family history", "Medication and antibiotics", "Birth mode and early life"]),
    ("Lifestyle & diet", ["Lifestyle", "Diet"]),
    ("Biomarkers", ["Inflammatory biomarkers", "Metabolism related biomarkers"]),
    ("Microbiome", ["Microbiome diversity"]),
    ("Red flags & surgical history", ["Red flags"]),
]


def entry_sections(form):
    """The seven nurse-facing form sections, shared by the add and edit patient pages."""
    grouped = dict(form.grouped())
    return [{"label": title, "fields": [f for g in names for f in grouped[g]],
             "has_errors": any(f.errors for g in names for f in grouped[g])}
            for title, names in ENTRY_SECTIONS]


class PatientForm(forms.Form):
    patient_code = forms.CharField(max_length=40, required=False, label="Patient ID",
                                   help_text="Leave blank to generate one.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bundle, _ = load_model()
        defaults, stats = bundle["defaults"], dataset_stats()
        self.groups = []
        for group, cols in GROUPS.items():
            names = []
            for f in cols:
                text = label(f) + (f" ({unit(f)})" if unit(f) and not choices_for(f) else "")
                opts = choices_for(f)
                if f in OPTIONAL:
                    self.fields[f] = self._optional_field(f, text, opts, stats.get(f))
                    names.append(f)
                    continue
                if opts:
                    init = defaults[f]
                    if f in BINARY_01_COLS:
                        init = "Yes" if str(init) in ("1", "1.0") else "No"
                    field = forms.ChoiceField(label=text, choices=[(o, o) for o in opts], initial=init)
                else:
                    s = stats[f]
                    kind = forms.IntegerField if s["integer"] else forms.FloatField
                    extra = {} if s["integer"] else {"widget": forms.NumberInput(attrs={"step": "any"})}
                    field = kind(label=text, min_value=s["min"], max_value=s["max"], **extra,
                                 initial=int(defaults[f]) if s["integer"] else round(defaults[f], 2),
                                 help_text=f"dataset range {s['min']:g}–{s['max']:g}")
                self.fields[f] = field
                names.append(f)
            self.groups.append((group, names))

    @staticmethod
    def _optional_field(f, text, opts, s):
        """Signs, symptoms and blood tests: optional, and blank unless recorded (the model imputes blanks)."""
        if opts:
            empty = "None / not recorded" if f in BLANK_MEANS_NONE else "Not recorded"
            return forms.ChoiceField(label=text, required=False, initial="",
                                     choices=[("", empty)] + [(o, o) for o in opts if o != "None"])
        if f in BLANK_MEANS_NONE:
            text += " — blank if no ongoing symptoms"
        kind = forms.IntegerField if s["integer"] else forms.FloatField
        extra = {} if s["integer"] else {"widget": forms.NumberInput(attrs={"step": "any"})}
        return kind(label=text, required=False, initial="", min_value=s["min"], max_value=s["max"], **extra,
                    help_text=f"optional · dataset range {s['min']:g}–{s['max']:g}")

    def grouped(self):
        return [(g, [self[f] for f in names]) for g, names in self.groups]

    def patient_data(self):
        data = {}
        for _, names in self.groups:
            for f in names:
                v = self.cleaned_data[f]
                if f in OPTIONAL and v in ("", None):
                    v = None
                elif f in BINARY_01_COLS or f in OPTIONAL_BINARY_COLS:
                    v = 1 if v == "Yes" else 0
                data[f] = v
        return data

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            try:
                encode(pd.DataFrame([self.patient_data()]))
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return cleaned


class PatientEditForm(PatientForm):
    """Update recorded values before a reassessment. The patient ID cannot be changed."""

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["patient_code"]
        data = patient.data if patient else {}
        for feature in FEATURES:
            if feature in data:
                value = data[feature]
                if value is None:
                    value = ""
                elif feature in BINARY_01_COLS or feature in OPTIONAL_BINARY_COLS:
                    value = "Yes" if str(value) in ("1", "1.0", "Yes") else "No"
                self.fields[feature].initial = value


class TreatmentForm(forms.ModelForm):
    class Meta:
        model = TreatmentEvent
        fields = ["medication", "start_date", "end_date", "note"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}),
                   "end_date": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and start > timezone.localdate():
            self.add_error("start_date", "The start date cannot be in the future.")
        if start and end and end < start:
            self.add_error("end_date", "The end date cannot be before the start date.")
        return cleaned


class MonitoringForm(forms.ModelForm):
    review_interval_weeks = forms.IntegerField(min_value=1, max_value=52, initial=12, label="Review every (weeks)")

    class Meta:
        model = MonitoringPlan
        fields = ["care_status", "review_interval_weeks", "active"]


YES_NO_UNKNOWN = [("unknown", "Not recorded"), ("yes", "Yes"), ("no", "No")]
TEST_RESULT = [("not_done", "Not done"), ("negative", "Negative"), ("positive", "Positive")]


class ReferralForm(forms.Form):
    """Symptoms and tests for referral rules. Separate from the 61 model inputs; everything may stay unknown."""
    diarrhoea_weeks = forms.FloatField(required=False, min_value=0, max_value=520, label="Diarrhoea duration (weeks)")
    bloody_stools_per_day = forms.IntegerField(required=False, min_value=0, max_value=50, label="Bloody stools per day")
    rectal_bleeding = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Rectal bleeding")
    abdominal_pain = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Abdominal pain")
    nocturnal_symptoms = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Nocturnal symptoms")
    weight_loss = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Unintentional weight loss")
    abdominal_or_rectal_mass = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Abdominal or rectal mass")
    recent_gastroenteritis_or_travel = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Recent gastroenteritis or travel")
    temperature_c = forms.FloatField(required=False, min_value=30, max_value=45, label="Temperature (°C)")
    pulse_bpm = forms.IntegerField(required=False, min_value=20, max_value=250, label="Pulse (beats/min)")
    haemoglobin_g_dl = forms.FloatField(required=False, min_value=1, max_value=25, label="Haemoglobin (g/dL)")
    iron_deficiency = forms.ChoiceField(choices=YES_NO_UNKNOWN, label="Iron deficiency")
    stool_infection_test = forms.ChoiceField(choices=TEST_RESULT, label="Stool infection test")
    celiac_serology = forms.ChoiceField(choices=TEST_RESULT, label="Celiac serology (tTG-IgA)")


class ReferralDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=[("accepted", "Accepted"), ("changed", "Changed"), ("not_needed", "Not needed")])
    decision_reason = forms.CharField(max_length=300, required=False, label="Reason")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") in ("changed", "not_needed") and not cleaned.get("decision_reason", "").strip():
            self.add_error("decision_reason", "Give a reason when you change or decline the suggestion.")
        return cleaned
