import json
from groq import Groq
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from services.models import Child_services, MainServices, Gender
from scheduler.models import DailySlot
from booking.models import Booking
from datetime import date, datetime, timedelta
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()
client = Groq(api_key=settings.GROQ_API_KEY)


def get_user_from_token(request):
    """Extract logged-in user from JWT token if present."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        token = auth_header.split(" ")[1]
        validated = AccessToken(token)
        user_id = validated["user_id"]
        return User.objects.get(id=user_id)
    except Exception:
        return None


def get_services_text():
    """Fetch all services from DB."""
    services_text = ""
    try:
        for gender in Gender.objects.all():
            services_text += f"\n{gender.name.upper()} SERVICES:\n"
            for main in MainServices.objects.filter(gender=gender):
                services_text += f"  {main.main_services_name}:\n"
                for child in Child_services.objects.filter(main_services=main):
                    services_text += (
                        f"    - {child.child_service_name}: "
                        f"₹{child.price}, {child.duration} mins\n"
                    )
    except Exception:
        services_text = "Services information temporarily unavailable."
    return services_text


def get_slots_for_date(target_date):
    """Fetch available slots for a specific date."""
    try:
        slots = DailySlot.objects.filter(
            slot_date=target_date,
            status='available'
        ).select_related('slot_master').order_by('slot_master__start_time')

        if slots.exists():
            slot_times = [
                f"{s.slot_master.start_time.strftime('%I:%M %p')} - "
                f"{s.slot_master.end_time.strftime('%I:%M %p')}"
                for s in slots
            ]
            return f"Available slots on {target_date.strftime('%A, %d %B')}: {', '.join(slot_times)}"
        else:
            return f"No available slots on {target_date.strftime('%A, %d %B')}."
    except Exception:
        return "Slot information temporarily unavailable."


def get_user_context(user):
    """Build context for logged-in user."""
    try:
        # Upcoming bookings
        upcoming = Booking.objects.filter(
            user=user,
            status__in=["pending", "confirmed"]
        ).select_related('start_slot__slot_master').prefetch_related('services__service')[:3]

        # Past bookings
        past = Booking.objects.filter(
            user=user,
            status="completed"
        ).order_by('-created_at')[:2]

        context = f"\nLOGGED IN USER: {user.username} (email: {user.email})\n"

        if upcoming.exists():
            context += "\nUPCOMING BOOKINGS:\n"
            for b in upcoming:
                service_names = ", ".join(
                    [bs.service.child_service_name for bs in b.services.all()]
                )
                slot = b.start_slot
                context += (
                    f"  - Booking #{b.id}: {service_names} | "
                    f"{slot.slot_date} {slot.slot_master.start_time.strftime('%I:%M %p')} | "
                    f"Status: {b.status} | Total: ₹{b.grand_total}\n"
                )
        else:
            context += "\nNo upcoming bookings.\n"

        if past.exists():
            context += "\nPAST BOOKINGS:\n"
            for b in past:
                service_names = ", ".join(
                    [bs.service.child_service_name for bs in b.services.all()]
                )
                context += f"  - {service_names} | Status: {b.status}\n"

        return context

    except Exception:
        return f"\nLOGGED IN USER: {user.username}\n"


def parse_date_from_message(messages):
    """
    Detect if user asked about a specific date.
    Returns a date object or None.
    """
    last_message = messages[-1].get("content", "").lower()
    today = date.today()

    if "today" in last_message:
        return today
    if "tomorrow" in last_message:
        return today + timedelta(days=1)

    # Day names
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if day in last_message:
            current_weekday = today.weekday()
            days_ahead = i - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    return None


def build_system_prompt(user=None, slot_date=None):
    """Dynamically builds system prompt."""
    services_text = get_services_text()

    # Slots section
    target_date = slot_date or date.today()
    slots_text = get_slots_for_date(target_date)

    # User context
    user_context = ""
    if user:
        user_context = get_user_context(user)
    else:
        user_context = "\nUSER: Not logged in. Encourage them to login to book.\n"

    return f"""You are a friendly and professional booking assistant for GlowUp Salon.

{user_context}

SERVICES WE OFFER:
{services_text}

AVAILABILITY:
{slots_text}

BOOKING POLICY:
- Bookings require user login
- Payment via Razorpay after booking confirmation
- Admin confirms bookings after submission
- Cancellations require 24 hours notice
- GST of 18% applied on all services

YOUR ROLE:
- Greet logged-in users by their name
- Help users check their booking status from the context above
- Guide users to book: login → select service → choose slot → pay
- Answer questions about availability for specific dates
- Recommend services based on what user asks
- Be warm, concise (2-3 sentences), professional
- For direct booking, guide them to the booking page
- If user asks about a specific date's slots, check the availability provided
"""


@csrf_exempt
@require_POST
def chat(request):
    try:
        body = json.loads(request.body)
        messages = body.get("messages", [])

        if not messages:
            return JsonResponse({"error": "No messages provided"}, status=400)

        # Get logged-in user from JWT
        user = get_user_from_token(request)

        # Detect date from message for slot checking
        slot_date = parse_date_from_message(messages)

        # Build smart system prompt
        system_prompt = build_system_prompt(user=user, slot_date=slot_date)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages
            ]
        )

        return JsonResponse({
            "reply": response.choices[0].message.content
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

from booking.models import Booking, BookingService, CartItem
from scheduler.models import DailySlot

@csrf_exempt
@require_POST
def book_via_chat(request):
    """Allow bot to create a booking directly."""
    try:
        user = get_user_from_token(request)
        if not user:
            return JsonResponse({"error": "Login required"}, status=401)

        body = json.loads(request.body)
        slot_id = body.get("slot_id")
        service_ids = body.get("service_ids", [])

        if not slot_id or not service_ids:
            return JsonResponse({"error": "slot_id and service_ids required"}, status=400)

        slot = DailySlot.objects.get(id=slot_id, status="available")
        services = Child_services.objects.filter(id__in=service_ids)

        if not services.exists():
            return JsonResponse({"error": "Invalid services"}, status=400)

        # Create booking
        booking = Booking.objects.create(
            user=user,
            start_slot=slot,
            status="pending"
        )

        # Add services
        for service in services:
            BookingService.objects.create(
                booking=booking,
                service=service,
                price=service.price,
                duration=service.duration,
                quantity=1
            )

        # Reserve slot
        slot.status = "reserved"
        slot.booked_by = user
        slot.save()

        # Calculate totals
        booking.calculate_totals()

        return JsonResponse({
            "success": True,
            "booking_id": booking.id,
            "grand_total": str(booking.grand_total),
            "message": f"Booking #{booking.id} created! Total: ₹{booking.grand_total}. Please complete payment."
        })

    except DailySlot.DoesNotExist:
        return JsonResponse({"error": "Slot not available"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)    




