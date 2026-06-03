from django.db import models

# ✅ Gender Table
class Gender(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )
    name = models.CharField(max_length=10, choices=GENDER_CHOICES, unique=True)

    def __str__(self):
        return self.name


# ✅ Main Services Table
class MainServices(models.Model):
    gender = models.ForeignKey(Gender, on_delete=models.PROTECT, related_name='main_services')
    main_services_name = models.CharField(max_length=100)
    main_services_description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('gender', 'main_services_name')

    def __str__(self):
        return f"{self.main_services_name} ({self.gender.name})"


# ✅ Child Services Table
class Child_services(models.Model):
    gender = models.ForeignKey(Gender, on_delete=models.PROTECT, null=True, blank=True)
    main_services = models.ForeignKey(MainServices, on_delete=models.PROTECT, related_name='child_services')
    child_service_name = models.CharField(max_length=100, default="Default Service")
    child_service_description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    duration = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.child_service_name} ({self.main_services.main_services_name} - {self.gender.name})"