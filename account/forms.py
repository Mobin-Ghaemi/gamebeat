from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class RejistViewForm (forms.Form):
    username = forms.CharField(label='نام کاربری  ',widget=forms.TextInput(attrs={'class':'form-control','placeholder':'نام کاربری خود را وارد کنید'}))
    email = forms.EmailField(label='ایمیل',widget=forms.EmailInput(attrs={'class':'form-control','placeholder':'ایمیل خود را وارد کنید'}))
    password = forms.CharField(label='رمز عبور',widget=forms.PasswordInput(attrs={'class':'form-control','placeholder' :'رمز عبور خود را وارد کنید'}))
    password1 = forms.CharField(label='تایید رمز عبور ',widget=forms.PasswordInput(attrs={'class':'form-control','placeholder' :'رمز عبور خود را وارد کنید'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        user = User.objects.filter(username=username).exists()
        if user:
            raise ValidationError('نام کاربری تکراری است')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        user = User.objects.filter(email=email).exists()
        if user : 
            raise ValidationError('ایمیل تکراری است')
        return email
    # def clean(self):
    #     if 'password' in self.cleaned_data and 'password1' in self.cleaned_data and self.cleaned_data['password'] != self.cleaned_data['password1']:
    #         raise forms.ValidationError("رمز عبور مطابقت ندارند  ")
    
    def clean(self):
        cd = super().clean()
        p1 = cd.get('password')
        p2 = cd.get('password1')
        if p1 and p2 and p1 != p2 :
            raise ValidationError ('رمز عبور مطابقت ندارد')
class LoginuserForm(forms.Form):
        username = forms.CharField(label='نام کاربری یا ایمیل ',widget=forms.TextInput(attrs={'class':'form-control','placeholder':'نام کاربری یا ایمیل  خود را وارد کنید'}))
        password = forms.CharField(label='رمز عبور',widget=forms.PasswordInput(attrs={'class':'form-control','placeholder' :'رمز عبور خود را وارد کنید'}))

class ResetPassword(forms.Form):
     coder = forms.CharField(max_length=30,label='کد ارسالی :')
class ChangePassword(forms.Form):
     newPassword = forms.CharField(max_length=30,label='رمز عبور جدید ')
     confirmPassword = forms.CharField(max_length=30,label='تایید رمز عبور')
     def clean(self):
        cd = super().clean()
        p1 = cd.get('newPassword')
        p2 = cd.get('confirmPassword')
        if p1 and p2 and p1 != p2 :
            raise ValidationError ('رمز عبور مطابقت ندارد')