from typing import Any
from django.shortcuts import render ,redirect,get_object_or_404
from django.http import HttpRequest, HttpResponse
from django.views import View
from account import models
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from . import forms
from django.utils.text import slugify
from django.contrib.auth.models import User


class Home(View):
    def get (self,request):
        post = models.Post.objects.order_by('-created','body',)
        return render(request , "home/index.html",{'post':post})
class PostDetail(View):
    def get(self,request, id, slug):
        post = get_object_or_404(models.Post,id=id,slug=slug)
        ctx = {
            'post':post,
        }
        return render(request,'home/detail.html', ctx)

class DeletePost(LoginRequiredMixin,View):
    def get(self,request,id):
        post = get_object_or_404(models.Post,id=id)
        username =request.user.username
        if post.user.username == request.user.username:
            post.delete()
            messages.success(request, 'پست شما با موفقیت حذف شد', 'warning') 
            
            return redirect('account:profile_user',username )
        else:
            messages.error(request, 'شما اجازه حذف این پست را ندارید', 'danger')
            return redirect('home:home')
class UpdatePost(LoginRequiredMixin, View):
    form_class = forms.PostCreateUpdateForm

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        self.post_instance =get_object_or_404(models.Post,pk=kwargs['id'])
        return super().setup(request, *args, **kwargs)
    def dispatch(self, request, *args, **kwargs):
        post = self.post_instance
        if not post.user.username == request.user.username:
            messages.error(request, "شما اجازه ی تغییر این پست را ندارید",'danger')
            return redirect('home:home')
        return super().dispatch(request, *args, **kwargs)
    def get(self, request,*args,**kwargs):
        postt =self.post_instance
        form = self.form_class(instance=postt)
        return render(request,'home/update.html', {'form': form})

    def post (self,request,*args,**kwargs):
        post = self.post_instance
        form = self.form_class(request.POST , instance=post)
        if form.is_valid():
            form.save()
            messages.success(request,'پست شما با موفقیت تغییر یافت','success')
            return redirect ('home:detail_post',post.id,post.slug)
class CreatePost(View):
    form_class = forms.PostCreateUpdateForm
    def get(self ,request,*args, **kwargs):
        form =self.form_class()
        return render(request,'home/create.html',{'form':form})
    def post(self ,request,*args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid(): 
            newPost = form.save(commit=False)
            newPost.user = request.user
            newPost.save()
            messages.success(request,'پست شما با موفقیت ثبت شد','success') 
            return redirect ('home:detail_post',newPost.id , newPost.slug)
        return render(request,'home/create.html',{'form':form})
    