"""
Firebase Admin SDK setup used to verify the Firebase ID token sent by the
Flutter app after Google sign-in.
"""

import firebase_admin
from django.conf import settings
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

_initialized = False


def _ensure_initialized():
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return

    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

    print("Firebase Admin initialized")
    print("FIREBASE_SERVICE_ACCOUNT_PATH:", settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    print("Firebase project_id from service account:", cred.project_id)

    _initialized = True


def verify_firebase_id_token(id_token: str) -> dict:
    """
    Verify and decode Firebase ID token.
    clock_skew_seconds helps when server/device clock differs slightly.
    """
    _ensure_initialized()
    return firebase_auth.verify_id_token(id_token, clock_skew_seconds=60)