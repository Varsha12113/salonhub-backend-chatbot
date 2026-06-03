# # scheduler/slot_reset.py

# from django.utils.timezone import now
# from scheduler.models import DailySlot
# from django.db.models import Q

# _last_reset_date = None

# def auto_reset_slots():
#     """
#     Resets slots daily at midnight.

#     ✔ booked → available (for today & future)
#     ✔ past dates → blocked
#     """

#     global _last_reset_date
#     today = now().date()

#     # Avoid running twice in same process day
#     if _last_reset_date == today:
#         return

#     # 1️⃣ Reset booked slots for TODAY & FUTURE
#     DailySlot.objects.filter(
#         Q(slot_date__gte=today) & Q(status__iexact="booked")
#     ).update(
#         status="available",
#         booked_by=None,
#         booked_service=None
#     )

#     # 2️⃣ Mark PAST slots as BLOCKED
#     DailySlot.objects.filter(
#         slot_date__lt=today
#     ).exclude(status="blocked").update(status="blocked")

#     _last_reset_date = today
#     print("DailySlot reset completed for:", today)

# scheduler/slot_reset.py (old logic)

from django.utils.timezone import now
from scheduler.models import DailySlot

def auto_reset_slots():
    """
    Only blocks genuinely past slots.
    Never touches booked or reserved slots —
    those are managed by booking and payment logic.
    """
    today = now().date()

    DailySlot.objects.filter(
        slot_date__lt=today
    ).exclude(
        status__in=["booked", "reserved", "blocked", "expired"]
    ).update(status="blocked")