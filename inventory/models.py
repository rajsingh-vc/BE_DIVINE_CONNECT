from django.db import models


class InventoryItem(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        LOW = "low", "Low"
        CRITICAL = "critical", "Critical"

    sku = models.CharField(max_length=20, unique=True)
    item_name = models.CharField(max_length=150)
    stock = models.PositiveIntegerField(default=0)
    min_threshold = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=30, default="pcs")
    dispatched_today = models.PositiveIntegerField(default=0)
    open_purchase_orders = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_name"]
        indexes = [models.Index(fields=["sku"])]

    @property
    def status(self):
        if self.stock < self.min_threshold * 0.5:
            return self.Status.CRITICAL
        if self.stock < self.min_threshold:
            return self.Status.LOW
        return self.Status.OK

    def __str__(self):
        return f"{self.sku} - {self.item_name}"