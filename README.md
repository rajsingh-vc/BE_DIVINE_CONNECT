# Sansthan Divine Ops — Backend (Django REST Framework)

## Stack
- Django 5 + Django REST Framework
- PostgreSQL
- JWT auth (djangorestframework-simplejwt)
- django-cors-headers, django-filter

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your Postgres credentials

# create the database (once):
createdb sansthan_db             # or: psql -c "CREATE DATABASE sansthan_db;"

python manage.py migrate
python manage.py createsuperuser  # or: python manage.py seed_demo_data
python manage.py runserver
```

The API is served at `http://localhost:8000/api/`. Django admin at `/admin/`.

## Apps / modules
`accounts`, `dashboard`, `devotees`, `volunteers`, `bookings` (+ sevas), `donations`,
`events` (+ visitors), `inventory`, `cms`, `reports`, `communication`, `platform_admin`.

Every app follows the same shape: `models.py` → `serializers.py` → `views.py` (DRF
ModelViewSet, CRUD + pagination + search + filtering) → `urls.py` (DefaultRouter).

## Auth endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/devotee/signup/` | Devotee signup |
| POST | `/api/auth/devotee/login/` | Devotee login (username or email) |
| POST | `/api/auth/volunteer/signup/` | Volunteer signup |
| POST | `/api/auth/volunteer/login/` | Volunteer login (username or email) |
| POST | `/api/auth/admin/login/` | Console admin login |
| POST | `/api/auth/login/` | Generic login (any user type) |
| POST | `/api/auth/forgot-password/` | Step 1: check email exists |
| POST | `/api/auth/reset-password/` | Step 2: set new password |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| GET  | `/api/auth/me/` | Current user |

## Volunteers module

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/volunteers/?status=pending` | Applications tab |
| GET | `/api/volunteers/?status=approved` | Review tab |
| GET | `/api/volunteers/?status=active` | Roster tab |
| GET | `/api/volunteers/?status=rejected` | Rejected tab |
| GET | `/api/volunteers/` | All volunteers (unfiltered), paginated |
| GET | `/api/volunteers/search/?q=...` | Instant search by name/ID |
| POST | `/api/volunteers/temporary/` | Register a Temporary volunteer — Name, Phone, Email, Reference Volunteer Name (must match an existing volunteer's name or the request is rejected with 400) |
| POST | `/api/volunteers/permanent/` | Register a Permanent volunteer — Name, Email, Home Address, Phone, Verification Type (`aadhaar`/`pan`/`driving_licence`), Verification Number, Photo. **Send as `multipart/form-data`** (photo upload or camera capture) |
| PATCH | `/api/volunteers/{id}/` | Edit any volunteer field (multipart if replacing the photo) |
| DELETE | `/api/volunteers/{id}/` | Delete a volunteer |
| POST | `/api/volunteers/{id}/approve/` | Approve a pending application |
| POST | `/api/volunteers/{id}/reject/` | Reject an application |
| POST | `/api/volunteers/{id}/review/` | Finalize into active roster (seva/shift/zone) |
| GET | `/api/volunteers/stats/` | Summary card counts (incl. temporary/permanent split) |

Volunteer photos are served from `/media/volunteer_photos/...` in development (`DEBUG=True`). In production, serve `MEDIA_ROOT` from your web server or an object store — Django does not serve media files itself when `DEBUG=False`.

## Devotees module

Standard CRUD (`GET/POST/PUT/PATCH/DELETE /api/devotees/`), plus `/api/devotees/search/?q=...`.
Devotees can either be self-registered (via `/api/auth/devotee/signup/`, which auto-creates the profile) or added directly by staff from the console with no login account — `user` is nullable on the model for this reason.

## Other modules (all support CRUD, `?search=`, pagination, filters)
- `/api/devotees/` (+ `/search/`)
- `/api/bookings/`, `/api/sevas/`
- `/api/donations/` (+ `/trend/`)
- `/api/events/`, `/api/visitors/`
- `/api/inventory/`
- `/api/cms/`
- `/api/reports/summary/`, `/api/reports/saved/`
- `/api/communication/`
- `/api/platform-admin/audit-logs/`, `/api/platform-admin/settings/`
- `/api/dashboard/stats/`, `/api/dashboard/visitor-flow/`, `/api/dashboard/revenue-mix/`,
  `/api/dashboard/alerts/`, `/api/dashboard/insights/`

## Notes
- All list endpoints are paginated (`?page=`), searchable (`?search=`) and filterable.
- Passwords are stored using Django's PBKDF2 hashing (`set_password`), never plaintext.
- `seed_demo_data` is optional and only for local development — remove/skip it in production.
