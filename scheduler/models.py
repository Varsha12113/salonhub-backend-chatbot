from django.db import models
from django.contrib.auth.models import User
from services.models import Child_services
from django.conf import settings


# 1. Working Days (Mon–Sun)
class WorkingDay(models.Model):
    weekday = models.IntegerField()  # 0 = Monday ... 6 = Sunday
    is_working = models.BooleanField(default=True)

    def __str__(self):
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return f"{days[self.weekday]} - {'Working' if self.is_working else 'Closed'}"

# 2. Holidays
class Holiday(models.Model):
    holiday_date = models.DateField(unique=True)
    reason = models.CharField(max_length=100, blank=True)
    

    def __str__(self):
        return f"{self.holiday_date} - {self.reason}"


# 3. Slot Template (Time slots repeated every day)
class SlotMaster(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

def clean(self):                                          # ← ADD THIS
    if self.start_time and self.end_time:
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)
        duration = (end_dt - start_dt).total_seconds() / 60

        if duration <= 0:
            raise ValidationError("end_time must be after start_time.")
        if duration > 120:
            raise ValidationError(
                f"Slot duration is {int(duration)} min — looks wrong. "
                "Max allowed is 120 min."
            )
    class Meta:
        unique_together = ('start_time', 'end_time')

    def __str__(self):
        return f"{self.start_time}-{self.end_time}"
    

# 4. Daily Slots (actual slots for each date)

class DailySlot(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('reserved',  'Reserved'), 
        ('booked', 'Booked'),
        ('blocked', 'Blocked'),
        ('expired', 'Expired'), 
    )

    slot_master = models.ForeignKey(SlotMaster, on_delete=models.CASCADE)
    slot_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_holiday = models.BooleanField(default=False)

    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    booked_service = models.ForeignKey(
        Child_services,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        unique_together = ('slot_master', 'slot_date')
        indexes = [
            models.Index(fields=['slot_date']),
        ]

    def __str__(self):
        return f"{self.slot_date} | {self.slot_master.start_time}-{self.slot_master.end_time} | {self.status}"


