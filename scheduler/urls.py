from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SlotMasterViewSet,
    HolidayViewSet,
    WorkingDayViewSet,
    DailySlotListAPIView,
    AvailableDatesAPIView,
    AdminDailySlotListAPIView,
)

router = DefaultRouter()
router.register(r'slotmasters', SlotMasterViewSet, basename='slotmaster')
router.register(r'holidays', HolidayViewSet, basename='holiday')
router.register(r'workingdays', WorkingDayViewSet, basename='workingday')

urlpatterns = [
    path('', include(router.urls)),
    path('slots/', DailySlotListAPIView.as_view(), name='daily-slots'),
    path('available-dates/', AvailableDatesAPIView.as_view(), name='available-dates'),
    path('admin/slots/', AdminDailySlotListAPIView.as_view(), name='admin-daily-slots'),
]
