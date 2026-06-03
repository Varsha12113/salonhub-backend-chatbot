# scheduler/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from .models import SlotMaster, DailySlot, Holiday, WorkingDay


def _is_closed(check_date):
    # Holiday check (Holiday model uses holiday_date)
    if Holiday.objects.filter(holiday_date=check_date).exists():
        return True

    # WorkingDay check if table has rows; if none => assume all days working
    if WorkingDay.objects.exists():
        wd = WorkingDay.objects.filter(weekday=check_date.weekday()).first()
        return bool(wd and not wd.is_working)

    return False


@receiver(post_save, sender=SlotMaster)
def ensure_slots_for_recent_days(sender, instance, created, **kwargs):
    """
    When a SlotMaster is created/updated → ensure DailySlot exists for
    today, tomorrow and day-after-tomorrow. If already exists, update
    status (unless booked).
    """
    today = timezone.localdate()
    dates = [today, today + timedelta(days=1), today + timedelta(days=2)]

    for d in dates:
        is_closed = _is_closed(d)
        default_status = "blocked" if is_closed else "available"

        obj, created_flag = DailySlot.objects.get_or_create(
            slot_master=instance,
            slot_date=d,
            defaults={
                "status": default_status,
                "is_holiday": is_closed,
            }
        )

        # If already exists and not booked, keep it in sync with working/holiday rules
        if not created_flag:
            if  obj.status not in ("booked", "reserved"):  # do not override booked slots
                obj.status = default_status
                obj.is_holiday = is_closed
                obj.save()

                
