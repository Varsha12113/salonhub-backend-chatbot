from rest_framework import viewsets, permissions, generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta, date,datetime

from .models import WorkingDay, Holiday, DailySlot

from .models import SlotMaster, WorkingDay, Holiday, DailySlot
from .serializers import (
    SlotMasterSerializer,
    WorkingDaySerializer,
    HolidaySerializer,
    DailySlotSerializer
)


class SlotMasterViewSet(viewsets.ModelViewSet):
    queryset = SlotMaster.objects.all().order_by("start_time")
    serializer_class = SlotMasterSerializer
    permission_classes = [permissions.IsAdminUser]


class WorkingDayViewSet(viewsets.ModelViewSet):
    queryset = WorkingDay.objects.all()
    serializer_class = WorkingDaySerializer
    permission_classes = [permissions.IsAdminUser]


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [permissions.IsAdminUser]


from rest_framework import status
from rest_framework.response import Response

class DailySlotListAPIView(generics.ListAPIView):
    serializer_class = DailySlotSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        date_str = self.request.query_params.get("date")

        if not date_str:
            return DailySlot.objects.none()

        # Parse date
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return DailySlot.objects.none()

        # Skip holiday date
        if Holiday.objects.filter(holiday_date=date_obj).exists():
            return DailySlot.objects.none()

        # Return available slots for date
        return DailySlot.objects.filter(
            slot_date=date_obj,
            is_holiday=False
        ).filter(status__iexact="available") \
        .select_related("slot_master") \
        .order_by("slot_master__start_time")

    def list(self, request, *args, **kwargs):
        date_str = request.query_params.get("date")

        if not date_str:
            return Response({"message": "date parameter is required"}, status=400)

        return super().list(request, *args, **kwargs)




class AvailableDatesAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        today = date.today()
        available_dates = []

        for i in range(0, 60):  # next 60 days
            current_date = today + timedelta(days=i)
            weekday = current_date.weekday()  # 0 = Monday ... 6 = Sunday

            # 1️⃣ Skip holidays
            if Holiday.objects.filter(holiday_date=current_date).exists():
                continue

            # 2️⃣ If WorkingDay table exists → use it
            if WorkingDay.objects.exists():
                wd = WorkingDay.objects.filter(weekday=weekday).first()
                if wd and not wd.is_working:
                    continue
            # else → assume ALL DAYS ARE WORKING

            # 3️⃣ Has at least 1 available slot?
            if DailySlot.objects.filter(
                slot_date=current_date,
                status__iexact="available",
                is_holiday=False
            ).exists():
                available_dates.append(str(current_date))

        return Response({"available_dates": available_dates})

# scheduler/views.py — add after AvailableDatesAPIView class

class AdminDailySlotListAPIView(generics.ListAPIView):
    serializer_class = DailySlotSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = None  # ← add this line to disable pagination

    def get_queryset(self):
        date_str = self.request.query_params.get("date")
        if not date_str:
            return DailySlot.objects.none()
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return DailySlot.objects.none()

        return DailySlot.objects.filter(
            slot_date=date_obj
        ).select_related("slot_master").order_by("slot_master__start_time")