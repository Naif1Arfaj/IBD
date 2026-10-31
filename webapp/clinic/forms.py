"""Patient entry form generated from the model's 10 input groups."""
import pandas as pd
from django import forms

from features import BINARY_01_COLS, GROUPS, encode
from predict import _load as load_model
from rag.queries import label, unit

from .services import choices_for, dataset_stats


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

    def grouped(self):
        return [(g, [self[f] for f in names]) for g, names in self.groups]

    def patient_data(self):
        data = {}
        for _, names in self.groups:
            for f in names:
                v = self.cleaned_data[f]
                data[f] = (1 if v == "Yes" else 0) if f in BINARY_01_COLS else v
        return data

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            try:
                encode(pd.DataFrame([self.patient_data()]))
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return cleaned
