from rest_framework import serializers
from .models import WorkingDay, Holiday, SlotMaster, DailySlot
from services.models import Child_services


class WorkingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingDay
        fields = '__all__'


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'


class SlotMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlotMaster
        fields = '__all__'


class DailySlotSerializer(serializers.ModelSerializer):
    slot_master = SlotMasterSerializer(read_only=True)
    booked_service = serializers.SerializerMethodField()
    booked_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DailySlot
        fields = [
            'id', 'slot_master', 'slot_date', 'status',
            'booked_by', 'booked_service'
        ]

    def get_booked_service(self, obj):
        if obj.booked_service:
            return {
                "id":   obj.booked_service.id,
                "name": obj.booked_service.child_service_name  # ← fix .name to .child_service_name
            }
        return None




