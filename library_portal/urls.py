"""
URL configuration for library_portal project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('circulation.urls')),
]

handler404 = 'circulation.views.handler404_view'
handler500 = 'circulation.views.handler500_view'
