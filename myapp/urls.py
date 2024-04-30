from django.urls import path
from . import views


app_name = 'home'
urlpatterns = [
    path ('',views.Home.as_view(),name ='home'),
    path ('post/<int:id>/<slug:slug>/',views.PostDetail.as_view(),name ='detail_post'),
    path('post/delete/<int:id>', views.DeletePost.as_view(), name='deletepost'),
    path('post/update/<int:id>',views.UpdatePost.as_view(),name = 'update_post'),
    path('post/create/',views.CreatePost.as_view(),name ='create_post')
]
