from django import forms
from account import models 


class PostCreateUpdateForm(forms.ModelForm):
    class Meta :
        model =  models.Post
        fields = ('body', )