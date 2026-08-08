# payments/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("razorpay/order/", views.create_razorpay_order, name="razorpay-create-order"),
    path("razorpay/verify/", views.verify_razorpay_payment, name="razorpay-verify-payment"),
]