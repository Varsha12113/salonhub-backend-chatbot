# booking/serializers.py
from rest_framework import serializers
from .models import CartItem, Booking, BookingService
from services.models import Child_services
from scheduler.models import DailySlot

# ---------------------
# Cart Serializers (unchanged)
# ---------------------
class CartItemSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.child_service_name', read_only=True)
    price = serializers.DecimalField(source='service.price', max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'service', 'service_name', 'quantity', 'price', 'subtotal']

    def get_subtotal(self, obj):
        return float(obj.service.price) * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem  # note: if you have Cart model, adjust accordingly; user code used CartItem only
        fields = ['id', 'user', 'items', 'total_price']

    def get_total_price(self, obj):
        # if Cart model exists, implement accordingly. Placeholder:
        return 0


# ---------------------
# Booking / BookingService Serializers
# ---------------------
class BookingServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.child_service_name', read_only=True)

    class Meta:
        model = BookingService
        fields = ['id', 'service', 'service_name', 'price', 'duration', 'quantity']


class BookingSerializer(serializers.ModelSerializer):
    services = BookingServiceSerializer(many=True, read_only=True)
    slot_info = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "username",
            "services",
            "slot_info",
            "total_price",
            "gst_amount",
            "grand_total",
            "status",
            "payment_status",       # new
            "razorpay_order_id",    # new
            "created_at",
        ]

    def get_slot_info(self, obj):
        sm = obj.start_slot.slot_master
        return {
            "date": obj.start_slot.slot_date,
            "start": sm.start_time,
            "end": sm.end_time,
        }



# ---------------------
# Create Booking Serializer (used by single endpoint)
# ---------------------
class CreateBookingSerializer(serializers.Serializer):
    start_slot_id = serializers.IntegerField()
    services = serializers.ListField(
        child=serializers.DictField(), allow_empty=False
    )

    def validate_start_slot_id(self, value):
        slot = DailySlot.objects.filter(id=value).first()
        if not slot:
            raise serializers.ValidationError("Slot not found.")
        if slot.status != "available":
            raise serializers.ValidationError("Slot is not available.")
        return value

    def validate(self, data):
        for s in data["services"]:
            service_id = s.get("service_id")
            if not Child_services.objects.filter(id=service_id).exists():
                raise serializers.ValidationError(f"Service {service_id} not found.")
        return data

