# GlowupSalon — Full Stack Salon Booking Application

A complete salon appointment booking system with online payments, admin management, and automated slot scheduling.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.x + Django REST Framework |
| Frontend | React.js + Redux Toolkit |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Payment | Razorpay (UPI + Cards) |
| Auth | JWT (Simple JWT) |
| Email | Gmail SMTP |
| Task Queue | Celery + Redis |
| Styling | Tailwind CSS |

---

## Features

### User
- Register and login with email or username
- Browse services by gender (Male / Female)
- Add services to cart
- 5-step booking wizard (Gender → Date → Slot → Details → Payment)
- Online payment via Razorpay (UPI, Cards, Netbanking)
- Automatic booking confirmation email
- View booking history

### Admin
- Accept or decline bookings
- Automatic refund on decline via Razorpay
- Email notification on new booking
- Manage services (Main + Child services with images)
- Manage slot masters (time templates)
- Configure working days
- Add / remove holidays
- View daily slot status (available, booked, reserved, blocked)
- Analytics dashboard (revenue, appointments, customer trends)

### Scheduler
- Auto-generates daily slots from SlotMaster templates
- Rolling window — generates 7 days ahead
- Expired slots auto-blocked
- Holiday slots auto-blocked
- Sunday closed by default
- 15-minute payment window — unpaid bookings auto-cancelled and slots freed

---

## Project Structure

```
salonhub_v2/
├── salonhub_B/          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/            # Custom user model, JWT auth
├── booking/             # Booking, cart, payment logic
│   ├── models.py        # Booking, BookingService, Payment, CartItem
│   ├── views.py         # Checkout, admin accept/decline, analytics
│   ├── payment_views.py # Razorpay order, verify, webhook
│   └── serializers.py
├── scheduler/           # Slot generation and management
│   ├── models.py        # SlotMaster, DailySlot, WorkingDay, Holiday
│   ├── tasks.py         # Celery tasks for slot generation
│   ├── signals.py       # Auto-create slots on SlotMaster save
│   └── slot_reset.py    # Midnight slot reset
├── services/            # Salon services catalog
│   ├── models.py        # Gender, MainServices, Child_services
│   └── views.py         # Admin CRUD + user public endpoints
└── requirements.txt
```

---

## Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Redis (for Celery)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/salonhub.git
cd salonhub_v2

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver
```

### Frontend Setup

```bash
cd salon-frontend

# Install dependencies
npm install

# Create .env file
echo "REACT_APP_API_URL=http://127.0.0.1:8000" > .env

# Start development server
npm start
```

### Celery Setup

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
celery -A salonhub_B worker -l info

# Terminal 3 — Celery beat (scheduled tasks)
celery -A salonhub_B beat -l info
```

---

## Environment Variables

Create a `.env` file in the Django project root:

```env
SECRET_KEY=your-django-secret-key

RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxxxxxx

EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

---

## Initial Data Setup

### Create slot masters (9am - 6pm, 30 min slots)

```bash
python manage.py shell
```

```python
from scheduler.models import SlotMaster, DailySlot, WorkingDay

DailySlot.objects.all().delete()
SlotMaster.objects.all().delete()

slots = [
    ("09:00", "09:30"), ("09:30", "10:00"), ("10:00", "10:30"),
    ("10:30", "11:00"), ("11:00", "11:30"), ("11:30", "12:00"),
    ("12:00", "12:30"), ("12:30", "13:00"), ("13:00", "13:30"),
    ("13:30", "14:00"), ("14:00", "14:30"), ("14:30", "15:00"),
    ("15:00", "15:30"), ("15:30", "16:00"), ("16:00", "16:30"),
    ("16:30", "17:00"), ("17:00", "17:30"), ("17:30", "18:00"),
]

for start, end in slots:
    SlotMaster.objects.create(start_time=start, end_time=end, is_active=True)
```

### Set working days

```python
from scheduler.models import WorkingDay

WorkingDay.objects.all().delete()

working_days = [
    (0, True), (1, True), (2, True), (3, True),
    (4, True), (5, True), (6, False),  # Sunday closed
]

for weekday, is_working in working_days:
    WorkingDay.objects.create(weekday=weekday, is_working=is_working)
```

### Generate slots

```python
from scheduler.tasks import generate_rolling_slots
generate_rolling_slots(window_days=7)
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register/` | User registration |
| POST | `/api/auth/admin/register/` | Admin registration |
| POST | `/api/auth/login/` | Login with email or username |
| POST | `/api/auth/logout/` | Logout |
| GET | `/api/auth/profile/` | Get user profile |
| GET | `/api/auth/admin/customers/dashboard/` | Admin customers dashboard |

### Services — User (Public)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/services/user/genders/` | List all genders |
| GET | `/api/services/user/main/?gender_id=<id>` | Main services by gender |
| GET | `/api/services/user/main/<main_service_id>/child/` | Child services under main |
| GET | `/api/services/user/child/<child_id>/` | Single child service detail |

### Services — Admin (Protected)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/services/admin/gender/<gender_id>/main/` | Create main service under gender |
| GET | `/api/services/admin/main/` | List all main services |
| GET | `/api/services/admin/main/<service_id>/` | Get single main service |
| PUT | `/api/services/admin/main/<service_id>/` | Update main service |
| PATCH | `/api/services/admin/main/<service_id>/` | Partial update main service |
| DELETE | `/api/services/admin/main/<service_id>/` | Delete main service |
| GET | `/api/services/admin/main/<main_service_id>/child/` | List child services |
| POST | `/api/services/admin/main/<main_service_id>/child/` | Create child service |
| GET | `/api/services/admin/main/<main_service_id>/child/<child_id>/` | Get child service |
| PUT | `/api/services/admin/main/<main_service_id>/child/<child_id>/` | Update child service |
| PATCH | `/api/services/admin/main/<main_service_id>/child/<child_id>/` | Partial update child service |
| DELETE | `/api/services/admin/main/<main_service_id>/child/<child_id>/` | Delete child service |

### Cart
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/booking/cart/add/<service_id>/` | Add service to cart |
| GET | `/api/booking/cart/` | View cart with totals |

### Booking
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/booking/checkout/` | Create booking + reserve slots |
| GET | `/api/booking/history/` | Booking history (admin) |

### Payment
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/booking/payment/create-order/` | Create Razorpay order |
| POST | `/api/booking/payment/verify/` | Verify payment signature |
| POST | `/api/booking/payment/webhook/` | Razorpay webhook handler |

### Admin — Booking Management
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/booking/admin/notifications/` | Unread notifications |
| POST | `/api/booking/admin/notifications/<id>/read/` | Mark notification as read |
| POST | `/api/booking/admin/accept/` | Accept booking |
| POST | `/api/booking/admin/decline/` | Decline booking + refund |

### Admin — Stats & Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/booking/admin/orders/stats/` | Order stats (total, completed, pending) |
| GET | `/api/booking/admin/sales/stats/` | Sales and revenue (last 24 hours) |
| GET | `/api/booking/admin/customers/trend/` | Customer visit trend (6 months) |
| GET | `/api/booking/admin/analytics/summary/` | Analytics overview |
| GET | `/api/booking/admin/analytics/monthly-revenue/` | Monthly revenue chart |
| GET | `/api/booking/admin/analytics/service-distribution/` | Service popularity pie chart |
| GET | `/api/booking/admin/analytics/appointments/` | Appointment stats |
| GET | `/api/booking/admin/analytics/new-customers/` | New customers this month |

### Scheduler
| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/api/scheduler/slotmasters/` | List / create slot masters |
| GET/PUT/DELETE | `/api/scheduler/slotmasters/<id>/` | Slot master detail |
| GET/POST | `/api/scheduler/workingdays/` | List / create working days |
| GET/PATCH | `/api/scheduler/workingdays/<id>/` | Update working day |
| GET/POST | `/api/scheduler/holidays/` | List / add holidays |
| DELETE | `/api/scheduler/holidays/<id>/` | Delete holiday |
| GET | `/api/scheduler/slots/?date=YYYY-MM-DD` | Available slots for date (user) |
| GET | `/api/scheduler/available-dates/` | Dates with available slots |
| GET | `/api/scheduler/admin/slots/?date=YYYY-MM-DD` | All slots for date (admin) |

---

## Payment Flow

```
1. User completes booking form
2. POST /booking/checkout/           → slots reserved, booking created
3. POST /payment/create-order/       → Razorpay order created
4. Razorpay popup opens              → user pays via UPI/card
5. POST /payment/verify/             → HMAC signature verified
6. Booking payment_status = paid
7. Admin reviews and accepts/declines
8. If accepted → booking confirmed, email sent to user
9. If declined → slots freed, refund initiated via Razorpay
```

---

## Slot States

```
available  → open for booking
reserved   → payment in progress (15 min window)
booked     → confirmed booking
blocked    → holiday or non-working day
expired    → past time slot
```

---


