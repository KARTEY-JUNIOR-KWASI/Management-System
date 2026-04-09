from django import forms
from .models import FeeCategory, FeeStructure
from core.models import Class

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control nexus-input-terminal',
                'placeholder': 'e.g. PTA Fee, Laboratory Fee',
                'style': 'height: 48px; border-radius: 12px;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control nexus-input-terminal',
                'rows': 3,
                'placeholder': 'Brief description of the fee purpose...',
                'style': 'border-radius: 12px;'
            }),
        }

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['class_name', 'category', 'amount']
        widgets = {
            'class_name': forms.Select(attrs={
                'class': 'form-select nexus-input-terminal',
                'style': 'height: 48px; border-radius: 12px;'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select nexus-input-terminal',
                'style': 'height: 48px; border-radius: 12px;'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control nexus-input-terminal',
                'step': '0.01',
                'placeholder': '0.00',
                'style': 'height: 48px; border-radius: 12px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['class_name'].queryset = Class.objects.all().order_by('grade', 'name')
        self.fields['category'].queryset = FeeCategory.objects.all().order_by('name')
