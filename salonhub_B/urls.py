"""
URL configuration for salonhub_B project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView


def home(request):
    return JsonResponse({
        "message": "Welcome to SalonHub API",
        "available_endpoints": [
            "/api/auth/",
            "/api/service/",
            "/api/chat/", 
            "/admin/"
        ]
    })

urlpatterns = [
    path('', home), 
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/services/', include('services.urls')), 
     # Scheduler app endpoints (SlotMaster, Holiday, WorkingDays, DailySlots)
    path('api/scheduler/', include('scheduler.urls')),
    path('api/booking/', include('booking.urls')),
    path('api/chat/', include('chatbot.urls')),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
