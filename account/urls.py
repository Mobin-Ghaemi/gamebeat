from django.urls import path
from . import views

app_name = 'account'
urlpatterns = [
    path('register/',views.RejistView.as_view(),name = 'register_user'),
    path('login/',views.loginUserView.as_view(),name ='login_user'),
    path('logout/',views.logoutView.as_view(),name ='logout_user'),
    path('profile/<str:username>',views.UserProfile.as_view(),name= 'profile_user'),

            #change password khodam
#     path('send/',views.randomCode,name='random_code'),
#     path('change/',views.changepassword,name='done_code'),
            #change password django
    # path("reset/",views.ResetPasword.as_view(),name="reset_password"),
    # path("reset/done/",views.ResetPasswordDone.as_view(),name= "password_reset_done"),
    # path('confirm/<uidb64>/<token>/',views.ResetPasswordConfirm.as_view(),name = "reset_password_confirm"),
    # path('confirm/complete',views.ResetPasswordComplete.as_view(),name='password_reset_complete'),
]