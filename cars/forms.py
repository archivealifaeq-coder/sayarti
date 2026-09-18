from django import forms

class OBDImportForm(forms.Form):
    excel_file = forms.FileField(label='اختر ملف Excel')
