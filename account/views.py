from typing import Any
from django.http import HttpRequest
from django.http.response import HttpResponse as HttpResponse
from django.views import View
from django.shortcuts import render ,redirect,get_object_or_404
from . import forms
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate,login , logout
from . import models
from .models import Post  # Import the Post model
from django.db.models import Count
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
import random


class RejistView(View):
    form_class = forms.RejistViewForm
    templateName = 'account/register.html'
    
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if request.user.is_authenticated:
            messages.success(request, 'شما قبلا ثبت نام کردید', 'danger') 
            return redirect('home:home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = self.form_class()
        return render(request, self.templateName, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Create the user
            user = User.objects.create_user(cd['username'], cd['email'], cd['password'])
            
            
            # Create a Post for the user with automatically generated slug
            Post.objects.create(user=user, body='', slug='')
            
            messages.success(request, 'حساب کاربری با موفقیت ساخته شد', 'success')
            return redirect('home:home')
        return render(request, self.templateName, {'form': form})

class loginUserView(View):
      formClass = forms.LoginuserForm
      templates_Name = 'account/login.html'
      def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any):
           if request.user.is_authenticated:
                  print('salam dispach')
                  messages.success(request,'شما قبلا وارد شدید  ','danger') 
                  return redirect ('home:home')
           return super().dispatch(request, *args, **kwargs)

      def get(self , request):
            form =self.formClass
            return render (request,self.templates_Name,{'form':form})
      def post (self , request):
            form = self.formClass(request.POST)
            if form.is_valid():
                  print('salam login')
                  cd = form.cleaned_data
                  user = authenticate(request,username = cd['username'] , password = cd['password'])
                  if user is not None :
                        login(request,user)
                        messages.success(request,'شما با موفقیت وارد شدید','success')
                        return redirect ('home:home')
            
            messages.success(request,'رمز عبور یا نام کاربری اشتباه است ','warning')
            return render (request,self.templates_Name,{'form':form})
class logoutView(View):
            def get (self ,request):
                        if  not request.user.is_authenticated:
                              messages.success(request,'لطفا ابتدا وارد شوید','danger')
                              return redirect ('account:login_user')
                        logout(request)
                        messages.success(request,"شما با موفقیت خارج شدید",'success')
                        return redirect ('home:home')
class UserProfile(View):
    def get(self, request, username):
        user = get_object_or_404(User,username=username)
        post = models.Post.objects.filter(user=user)
        user_counts = post.count()
        

        # count = None
        # for x in user_counts:
        #     count = x.post_count
        #     print(x,x.post_count) 
        ctx = {
            'user': user,
            'post': post,
            'user_count': user_counts,
        }
        return render(request, 'account/profile.html', ctx)
            #change password django
# class ResetPasword(auth_views.PasswordResetView):
#       template_name = 'account/password_reset.html'
#       success_url = reverse_lazy('account/password_reset_done')
#       email_template_name = 'account/password_reset_email.html'
# class ResetPasswordDone(auth_views.PasswordResetDoneView):
#       template_name = 'account/reset_password_done'
# class ResetPasswordConfirm(auth_views.PasswordResetConfirmView):
#       template_name = 'account/password_reset_confirm'
#       success_url = reverse_lazy('account/password_reset_complete')
# class ResetPasswordComplete(auth_views.PasswordResetCompleteView):
#       template_name = 'account/password_reset_complete'
            #change password khodam 
# def randomCode (request):
#       code='1234'
#       if request.method =='GET':
#             form = forms.ResetPassword
#             return render(request,'account/resetpassword/send.html',{'form':form})
#       if request.method =='POST':
#             form = forms.ResetPassword(request.POST)
#             if request.POST.get('coder') == code:
#                   messages.success(request,'صحت سنجی شما تایید شد','success')
#                   return redirect ('account:done_code')
#             else :
#                   messages.success(request,'کد ورودی اشتباه است ','danger')
            
#       return render(request,'account/resetpassword/send.html',{'form':form})
# def changepassword(request):
#     if request.method == 'GET':
#         form = forms.ChangePassword()
#         return render(request, 'account/resetpassword/reset.html', {'form': form})
#     if request.method == 'POST':
#         form = forms.ChangePassword(request.POST)
#         cd = form.cleaned_data 
#         if form.is_valid():
#             user = request.user  
#             MOBIN =user.set_password(form(request.POST))
#             MOBIN.save()  
#             print(MOBIN)
#             messages.success(request, 'رمز عبور شما با موفقیت تغییر یافت','success')
#             return redirect('account:login_user')
#         else:
#             messages.success(request, 'رمز های عبور تطابق ندارند ! الطفا دوباره تلاش کنید','danger')
#             return render(request, 'account/resetpassword/reset.html', {'form': form})
        