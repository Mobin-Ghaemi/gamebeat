from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class PersianUserCreationForm(UserCreationForm):
    error_messages = {
        'password_mismatch': _('دو رمز عبور با هم مطابقت ندارند.'),
    }

    class Meta:
        model = User
        fields = ('username',)
        error_messages = {
            'username': {
                'required': _('وارد کردن نام کاربری الزامی است.'),
                'unique': _('این نام کاربری قبلاً ثبت شده است.'),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('نام کاربری')
        self.fields['username'].error_messages.update({
            'required': _('وارد کردن نام کاربری الزامی است.'),
        })
        self.fields['password1'].label = _('رمز عبور')
        self.fields['password1'].error_messages.update({
            'required': _('وارد کردن رمز عبور الزامی است.'),
        })
        self.fields['password2'].label = _('تکرار رمز عبور')
        self.fields['password2'].error_messages.update({
            'required': _('تکرار رمز عبور الزامی است.'),
        })


class PersianAuthenticationForm(AuthenticationForm):
    error_messages = {
        'invalid_login': _(
            'نام کاربری یا رمز عبور درست نیست. دقت کن که حروف بزرگ و کوچک با هم فرق دارند.'
        ),
        'inactive': _('این حساب کاربری غیرفعال شده است.'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('نام کاربری')
        self.fields['username'].error_messages.update({
            'required': _('وارد کردن نام کاربری الزامی است.'),
        })
        self.fields['password'].label = _('رمز عبور')
        self.fields['password'].error_messages.update({
            'required': _('وارد کردن رمز عبور الزامی است.'),
        })
