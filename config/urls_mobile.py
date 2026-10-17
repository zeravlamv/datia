from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from datia.api.api import api
from datia.views import mobile_dashboard_view, mobile_login_view, mobile_health_view, logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path('login/', mobile_login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('health/', mobile_health_view, name='mobile_health'),
    path('', mobile_dashboard_view, name='mobile'),
]
