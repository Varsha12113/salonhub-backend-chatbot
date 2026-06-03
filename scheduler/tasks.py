from django.utils import timezone
from datetime import timedelta
from celery import shared_task
from django.db import transaction

from .models import SlotMaster, DailySlot, WorkingDay, Holiday

@shared_task
def generate_rolling_slots(window_days=3):

    today = timezone.localdate()
    now_time = timezone.localtime().time()

    # 1️⃣ DELETE YESTERDAY'S SLOTS
    yesterday = today - timedelta(days=1)
    DailySlot.objects.filter(slot_date__lt=today).delete()

    # 2️⃣ EXPIRE TODAY'S PAST TIME SLOTS
    DailySlot.objects.filter(
        slot_date=today,
        status__in=["available", "blocked"],
        slot_master__end_time__lt=now_time
    ).update(status="expired")

    # 3️⃣ CALCULATE THE ROLLING DATES (today + next days)
    dates = [today + timedelta(days=i) for i in range(window_days)]
    masters = SlotMaster.objects.filter(is_active=True)

    for date in dates:
        weekday = date.weekday()
        is_holiday = Holiday.objects.filter(holiday_date=date).exists()
        wd = WorkingDay.objects.filter(weekday=weekday).first()
        is_closed = bool(wd and not wd.is_working)

        # default slot status
        default_status = "blocked" if (is_holiday or is_closed) else "available"

        with transaction.atomic():
            for sm in masters:
                slot = DailySlot.objects.filter(slot_master=sm, slot_date=date).first()

                # 4️⃣ CREATE NEW SLOTS IF NOT EXISTS
                if not slot:
                    DailySlot.objects.create(
                        slot_master=sm,
                        slot_date=date,
                        status=default_status,
                        is_holiday=is_holiday,
                    )
                    continue

                # 5️⃣ DO NOT TOUCH BOOKED SLOTS
                if slot.status in ("booked", "reserved"):
                  continue

                # 6️⃣ TODAY: handle expired/future
                if date == today:
                    if sm.end_time < now_time:
                        slot.status = "expired"
                    else:
                        slot.status = default_status
                else:
                    # FUTURE DATES → ALWAYS REFRESH
                    slot.status = default_status

                slot.is_holiday = is_holiday
                slot.save()

    return "SUCCESS: New day created & old day removed"

@shared_task
def watch_and_expire_slots():
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    # Expire today’s past-time slots (NOT booked)
    DailySlot.objects.filter(
        slot_date=today,
        status__in=["available", "blocked"],
        slot_master__end_time__lt=now_time
    ).update(status="expired")

    return "Expired today's finished slots"


# 2. Add this new task at the bottom of the file:
@shared_task
def expire_reserved_slots():
    """
    Runs every 5 minutes.
    Finds bookings where payment was never completed
    within 15 minutes and frees their slots.
    """
    from booking.models import Booking
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(minutes=15)

    stale_bookings = Booking.objects.filter(
        status="pending",
        payment_status="pending",
        created_at__lt=cutoff
    ).select_related("start_slot__slot_master")

    freed = 0
    for booking in stale_bookings:
        from booking.views import compute_required_slot_master_ids

        total_minutes = sum(
            bs.service.duration for bs in booking.services.all()
        )
        slot_masters = SlotMaster.objects.filter(
            is_active=True
        ).order_by("start_time")

        needed = compute_required_slot_master_ids(
            booking.start_slot.slot_master,
            slot_masters,
            total_minutes
        )

        DailySlot.objects.filter(
            slot_master_id__in=needed,
            slot_date=booking.start_slot.slot_date,
            status="reserved"
        ).update(
            status="available",
            booked_by=None,
            booked_service=None
        )

        booking.status = "cancelled"
        booking.save(update_fields=["status"])
        freed += 1

    return f"Expired {freed} stale bookings"