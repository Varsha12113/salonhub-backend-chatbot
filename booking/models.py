from django.db import models
from django.conf import settings
from scheduler.models import DailySlot
from services.models import Child_services
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


# Slot reservation duration before admin approval
RESERVATION_MINUTES = 15   # slot auto free after 15min if admin not approved


# ------------------------------
# 1) CART ITEM
# ------------------------------
class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )
    service = models.ForeignKey(
        Child_services,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('user', 'service')

    def __str__(self):
        return f"{self.user.username} → {self.service.child_service_name}"


# ------------------------------
# 2) BOOKING
# ------------------------------
class Booking(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),         # User submitted, admin must approve
        ("confirmed", "Confirmed"),     # Admin accepted
        ("declined", "Declined"),       # Admin rejected
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    # ── Payment status constants ──
    PAYMENT_PENDING  = "pending"
    PAYMENT_PAID     = "paid"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_FAILED   = "failed"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING,  "Pending"),
        (PAYMENT_PAID,     "Paid"),
        (PAYMENT_REFUNDED, "Refunded"),
        (PAYMENT_FAILED,   "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    start_slot = models.ForeignKey(
        DailySlot,
        on_delete=models.CASCADE,
        related_name="booking_start_slot"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ── Billing ──
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5,  decimal_places=2, default=18)
    gst_amount  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Payment fields (new) ──
    payment_status      = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING
    )
    razorpay_order_id   = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature  = models.CharField(max_length=255, blank=True, null=True)

    def calculate_totals(self):
        # ── Fixed: multiply by quantity ──
        base = sum(
            item.price * item.quantity        # use snapshot price, not live price
            for item in self.services.all()
        )
        gst_rate    = self.gst_percent / Decimal("100")
        gst         = base * gst_rate
        self.total_price = base
        self.gst_amount  = gst
        self.grand_total = base + gst
        self.save(update_fields=["total_price", "gst_amount", "grand_total"])

    def __str__(self):
        return f"Booking #{self.id} - {self.user.username} ({self.status})"

# ------------------------------
# 3) SELECTED SERVICES INSIDE BOOKING
# ------------------------------
class BookingService(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='services'
    )
    service = models.ForeignKey(
        Child_services,
        on_delete=models.PROTECT
    )
    # ── Snapshot fields (new) ──
    price    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration = models.PositiveIntegerField(default=30)
    quantity = models.PositiveIntegerField(default=1)


    def __str__(self):
        return f"{self.booking.id} → {self.service.child_service_name}"
# ------------------------------
# 4) PAYMENT — new model
# ------------------------------
class Payment(models.Model):
    booking             = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="payment"
    )
    amount              = models.DecimalField(max_digits=12, decimal_places=2)
    currency            = models.CharField(max_length=10, default="INR")
    razorpay_order_id   = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_refund_id  = models.CharField(max_length=100, blank=True)
    paid_at             = models.DateTimeField(null=True, blank=True)
    refunded_at         = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Booking #{self.booking.id} — {self.amount} {self.currency}"

class AdminNotification(models.Model):
    NOTIF_BOOKING = "BOOKING"

    TYPE_CHOICES = (
        (NOTIF_BOOKING, "New Booking"),
    )

    booking = models.ForeignKey(
        "Booking",  # avoids circular import issues
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=NOTIF_BOOKING)
    message = models.CharField(max_length=255)

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"is_staff": True},
        related_name="read_notifications"
    )

    def __str__(self):
        return f"Notification #{self.id} - {self.message[:25]}"

