# booking/payment_views.py

import razorpay
import hmac
import hashlib
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from .models import Booking, Payment
from scheduler.models import DailySlot

client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


def _free_booking_slots(booking):
    """Free all slots tied to a booking back to available."""
    from booking.views import compute_required_slot_master_ids
    from scheduler.models import SlotMaster

    total_minutes = sum(
        bs.service.duration for bs in booking.services.all()
    )
    slot_masters = SlotMaster.objects.filter(
        is_active=True
    ).order_by("start_time")
    needed = compute_required_slot_master_ids(
        booking.start_slot.slot_master, slot_masters, total_minutes
    )
    DailySlot.objects.filter(
        slot_master_id__in=needed,
        slot_date=booking.start_slot.slot_date
    ).update(
        status="available",
        booked_by=None,
        booked_service=None
    )


# ─────────────────────────────────────────
# STEP 1 — Create Razorpay order
# POST /booking/payment/create-order/
# Called by frontend right after checkout
# ─────────────────────────────────────────
class CreatePaymentOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        booking_id = request.data.get("booking_id")

        try:
            booking = Booking.objects.get(
                id=booking_id, user=request.user
            )
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        if booking.payment_status == Booking.PAYMENT_PAID:
            return Response({"detail": "Already paid"}, status=400)

        if booking.status == "cancelled":
            return Response(
                {"detail": "Booking expired, please book again"},
                status=400
            )

        # Amount in paise
        amount_paise = int(booking.grand_total * 100)

        razorpay_order = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  f"booking_{booking.id}",
            "notes": {
                "booking_id": str(booking.id),
                "user":       request.user.username,
            }
        })

        booking.razorpay_order_id = razorpay_order["id"]
        booking.save(update_fields=["razorpay_order_id"])

        Payment.objects.update_or_create(
            booking=booking,
            defaults={
                "amount":            booking.grand_total,
                "currency":          "INR",
                "razorpay_order_id": razorpay_order["id"],
            }
        )

        return Response({
            "razorpay_order_id": razorpay_order["id"],
            "amount":            amount_paise,
            "currency":          "INR",
            "key":               settings.RAZORPAY_KEY_ID,
            "booking_id":        booking.id,
            "name":              "Salon Booking",
            "description":       f"Booking #{booking.id}",
            "prefill": {
                "name":  request.user.username,
                "email": request.user.email,
            }
        })


# ─────────────────────────────────────────
# STEP 2 — Verify payment
# POST /booking/payment/verify/
# Called by React after Razorpay popup closes
# ─────────────────────────────────────────
class VerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        razorpay_order_id   = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature  = request.data.get("razorpay_signature")

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response(
                {"detail": "Missing payment fields"}, status=400
            )

        # Verify HMAC signature
        body     = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, razorpay_signature):
            return Response(
                {"detail": "Invalid payment signature"}, status=400
            )

        try:
            booking = Booking.objects.get(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            )
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        with transaction.atomic():
            booking.payment_status      = Booking.PAYMENT_PAID
            booking.razorpay_payment_id = razorpay_payment_id
            booking.razorpay_signature  = razorpay_signature
            booking.save(update_fields=[
                "payment_status",
                "razorpay_payment_id",
                "razorpay_signature"
            ])

            Payment.objects.filter(booking=booking).update(
                razorpay_payment_id=razorpay_payment_id,
                paid_at=timezone.now()
            )

        return Response({
            "detail":         "Payment verified successfully",
            "booking_id":     booking.id,
            "status":         booking.status,
            "payment_status": booking.payment_status,
        })


# ─────────────────────────────────────────
# STEP 3 — Razorpay webhook
# POST /booking/payment/webhook/
# Called by Razorpay server — not the user
# ─────────────────────────────────────────
class RazorpayWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        received_sig   = request.headers.get("X-Razorpay-Signature", "")

        body     = request.body
        expected = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, received_sig):
            return Response(
                {"detail": "Invalid webhook signature"}, status=400
            )

        payload = request.data
        event   = payload.get("event")
        entity  = payload.get("payload", {}).get(
            "payment", {}
        ).get("entity", {})

        # Backup confirmation if verify endpoint was missed
        if event == "payment.captured":
            order_id   = entity.get("order_id")
            payment_id = entity.get("id")
            try:
                booking = Booking.objects.get(razorpay_order_id=order_id)
                if booking.payment_status != Booking.PAYMENT_PAID:
                    booking.payment_status      = Booking.PAYMENT_PAID
                    booking.razorpay_payment_id = payment_id
                    booking.save(update_fields=[
                        "payment_status", "razorpay_payment_id"
                    ])
                    Payment.objects.filter(booking=booking).update(
                        razorpay_payment_id=payment_id,
                        paid_at=timezone.now()
                    )
            except Booking.DoesNotExist:
                pass

        # Refund confirmed
        elif event == "refund.processed":
            refund_entity = payload.get("payload", {}).get(
                "refund", {}
            ).get("entity", {})
            payment_id = refund_entity.get("payment_id")
            refund_id  = refund_entity.get("id")
            try:
                booking = Booking.objects.get(
                    razorpay_payment_id=payment_id
                )
                booking.payment_status = Booking.PAYMENT_REFUNDED
                booking.save(update_fields=["payment_status"])
                Payment.objects.filter(booking=booking).update(
                    razorpay_refund_id=refund_id,
                    refunded_at=timezone.now()
                )
            except Booking.DoesNotExist:
                pass

        # Payment failed — free the slots
        elif event == "payment.failed":
            order_id = entity.get("order_id")
            try:
                booking = Booking.objects.get(razorpay_order_id=order_id)
                booking.payment_status = Booking.PAYMENT_FAILED
                booking.status         = "cancelled"
                booking.save(update_fields=["payment_status", "status"])
                _free_booking_slots(booking)
            except Booking.DoesNotExist:
                pass

        return Response({"detail": "ok"})