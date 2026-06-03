from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework import status, parsers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from accounts.permissions import IsAdmin
from django.db.models.deletion import ProtectedError
from .models import Gender, MainServices, Child_services
from .serializers import (
    GenderSerializer,
    MainServicesSerializer,
    ChildServiceSerializer
)

def _has_active_bookings(child_service):
    """Check if service is used in any active booking."""
    from booking.models import BookingService
    return BookingService.objects.filter(
        service=child_service,
        booking__status__in=["pending", "confirmed"]
    ).exists()
# -------------------------
# USER PUBLIC VIEWS (No auth)
# -------------------------
class UserGenderListView(APIView):
    permission_classes = [AllowAny]
 
    def get(self, request):
        genders = Gender.objects.all()
        serializer = GenderSerializer(genders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserMainServicesByGenderView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        gender_id = request.query_params.get('gender_id')
        if not gender_id:
            return Response({"error": "gender_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        services = MainServices.objects.filter(gender_id=gender_id).select_related('gender')
        if not services.exists():
            return Response({"message": "No main services found for this gender"}, status=status.HTTP_404_NOT_FOUND)

        serializer = MainServicesSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserChildServicesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, main_service_id):
        children = Child_services.objects.filter(main_services_id=main_service_id).select_related('main_services', 'gender')
        if not children.exists():
            return Response({"message": "No child services found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChildServiceSerializer(children, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserSingleChildServiceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, child_id):
        child = get_object_or_404(Child_services, pk=child_id)
        serializer = ChildServiceSerializer(child, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------
# ADMIN: MAIN SERVICES CRUD
# -------------------------
class AdminMainUnderGenderView(APIView):
    """
    POST: Create a main service under a gender (gender_id from URL)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, gender_id):
        gender = get_object_or_404(Gender, pk=gender_id)

        # Basic required fields
        name = request.data.get('main_services_name')
        if not name:
            return Response({"main_services_name": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        # enforce unique per gender
        qs = MainServices.objects.filter(gender=gender, main_services_name__iexact=name)
        if qs.exists():
            return Response({"non_field_errors": ["A main service with this name already exists for this gender."]},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = MainServicesSerializer(data=request.data)
        if serializer.is_valid():
            # save and attach gender (because serializer's field gender is read-only)
            main = MainServices.objects.create(
                gender=gender,
                main_services_name=serializer.validated_data['main_services_name'],
                main_services_description=serializer.validated_data.get('main_services_description', '')
            )
            return Response({"message": "Main service created", "data": MainServicesSerializer(main).data},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminMainServicesView(APIView):
    """
    GET list + POST handled by AdminMainUnderGenderView
    GET single, PUT, PATCH, DELETE for main services
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, service_id=None):
        if service_id:
            obj = get_object_or_404(MainServices, pk=service_id)
            serializer = MainServicesSerializer(obj)
            return Response(serializer.data, status=status.HTTP_200_OK)

        services = MainServices.objects.all().select_related('gender')
        serializer = MainServicesSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, service_id):
        obj = get_object_or_404(MainServices, pk=service_id)
        serializer = MainServicesSerializer(obj, data=request.data, partial=False)
        if serializer.is_valid():
            # We don't allow changing gender via this endpoint (design choice).
            obj.main_services_name = serializer.validated_data['main_services_name']
            obj.main_services_description = serializer.validated_data.get('main_services_description', '')
            # enforce unique per gender on update
            conflict = MainServices.objects.filter(
                gender=obj.gender,
                main_services_name__iexact=obj.main_services_name
            ).exclude(pk=obj.pk)
            if conflict.exists():
                return Response({"non_field_errors": ["A main service with this name already exists for this gender."]},
                                status=status.HTTP_400_BAD_REQUEST)
            obj.save()
            return Response({"message": "Main service updated", "data": MainServicesSerializer(obj).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, service_id):
        obj = get_object_or_404(MainServices, pk=service_id)
        serializer = MainServicesSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            name = serializer.validated_data.get('main_services_name', obj.main_services_name)
            desc = serializer.validated_data.get('main_services_description', obj.main_services_description)
            # uniqueness check
            conflict = MainServices.objects.filter(gender=obj.gender, main_services_name__iexact=name).exclude(pk=obj.pk)
            if conflict.exists():
                return Response({"non_field_errors": ["A main service with this name already exists for this gender."]},
                                status=status.HTTP_400_BAD_REQUEST)
            obj.main_services_name = name
            obj.main_services_description = desc
            obj.save()
            return Response({"message": "Main service partially updated", "data": MainServicesSerializer(obj).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, service_id):
        obj = get_object_or_404(MainServices, pk=service_id)
        obj.delete()
        return Response({"message": "Main service deleted"}, status=status.HTTP_204_NO_CONTENT)


# -------------------------
# ADMIN: CHILD SERVICES (scoped to main)
# -------------------------
class AdminChildServiceView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get(self, request, main_service_id):
        children = Child_services.objects.filter(main_services_id=main_service_id).select_related('main_services', 'gender')
        serializer = ChildServiceSerializer(children, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, main_service_id):
        main = get_object_or_404(MainServices, pk=main_service_id)
        gender = main.gender  # inherit

        # Validate basic required fields
        name = request.data.get('child_service_name')
        price = request.data.get('price')
        if not name:
            return Response({"child_service_name": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if not price:
            return Response({"price": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        # Create via serializer (so we reuse validation)
        serializer = ChildServiceSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # create using model create to ensure gender and main are correctly set
            child = Child_services.objects.create(
                main_services=main,
                gender=gender,
                child_service_name=serializer.validated_data['child_service_name'],
                child_service_description=serializer.validated_data.get('child_service_description', ''),
                price=serializer.validated_data['price'],
                duration=serializer.validated_data.get('duration', 30),
                image=request.FILES.get('image')  # MultiPartParser supports file
            )
            return Response({"message": "Child service created successfully",
                             "data": ChildServiceSerializer(child, context={'request': request}).data},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminChildServiceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_object(self, main_service_id, child_id):
        return get_object_or_404(
            Child_services,
            pk=child_id,
            main_services_id=main_service_id
        )

    def get(self, request, main_service_id, child_id):
        child = self.get_object(main_service_id, child_id)
        serializer = ChildServiceSerializer(child, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, main_service_id, child_id):
        child = self.get_object(main_service_id, child_id)
        # ← removed _has_active_bookings check, editing always allowed

        serializer = ChildServiceSerializer(
            child, data=request.data, partial=False, context={'request': request}
        )
        if serializer.is_valid():
            for field, value in serializer.validated_data.items():
                setattr(child, field, value)
            if 'image' in request.FILES:
                child.image = request.FILES['image']
            child.save()
            return Response(
                {"message": "Child service updated",
                "data": ChildServiceSerializer(child, context={'request': request}).data},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def patch(self, request, main_service_id, child_id):
        child = self.get_object(main_service_id, child_id)
        # ← removed _has_active_bookings check, editing always allowed

        serializer = ChildServiceSerializer(
            child, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            for field, value in serializer.validated_data.items():
                setattr(child, field, value)
            if 'image' in request.FILES:
                child.image = request.FILES['image']
            child.save()
            return Response(
                {"message": "Child service partially updated",
                "data": ChildServiceSerializer(child, context={'request': request}).data},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request, main_service_id, child_id):
        child = self.get_object(main_service_id, child_id)

        # ← only block deletion if active bookings exist
        if _has_active_bookings(child):
            return Response(
                {"error": "Cannot delete a service that has active bookings."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            child.delete()
            return Response(
                {"message": "Child service deleted"},
                status=status.HTTP_200_OK
            )
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this service because it is used in a booking."},
                status=status.HTTP_400_BAD_REQUEST
            )
