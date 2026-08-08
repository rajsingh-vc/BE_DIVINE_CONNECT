from django.conf import settings
from django.db import models


from django.conf import settings
from django.db import models
from django.utils.text import slugify

# from .models import TempleInfo


import re


def youtube_id_from_url(url: str) -> str | None:
    """Extract the 11-character YouTube video ID from common URL shapes."""
    patterns = [
        r"youtube\.com/watch\?v=([\w-]{11})",
        r"youtu\.be/([\w-]{11})",
        r"youtube\.com/embed/([\w-]{11})",
        r"youtube\.com/shorts/([\w-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


class VideoItem(models.Model):
    class SourceType(models.TextChoices):
        YOUTUBE = "youtube", "YouTube"
        UPLOAD = "upload", "Uploaded File"

    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    youtube_url = models.URLField(blank=True, default="")
    youtube_video_id = models.CharField(max_length=20, blank=True, default="")
    file = models.FileField(upload_to="videos/%Y/%m/", blank=True, null=True)
    thumbnail = models.ImageField(upload_to="videos/thumbnails/", blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="video_uploads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["source_type"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.source_type == self.SourceType.YOUTUBE and self.youtube_url:
            vid = youtube_id_from_url(self.youtube_url)
            if vid:
                self.youtube_video_id = vid
        super().save(*args, **kwargs)

class NewsPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    excerpt = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    photo = models.ImageField(upload_to="news/%Y/%m/", blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PUBLISHED
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_posts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:260]
            slug = base_slug
            counter = 1
            while NewsPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

class ContentPage(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    body = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["slug"]), models.Index(fields=["status"])]

    def __str__(self):
        return self.title


class Announcement(models.Model):
    """A CMS 'Notification Template' send. Creating one fans out a
    Notification to every volunteer's bell — see AnnouncementViewSet.
    """
    class Type(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        IMPORTANT = "important", "Important"

    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_announcements"
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["type"]), models.Index(fields=["sent_at"])]

    def __str__(self):
        return f"{self.get_type_display()} — {self.title}"



class GalleryItem(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    media_type = models.CharField(max_length=10, choices=MediaType.choices)
    file = models.FileField(upload_to="gallery/")
    thumbnail = models.ImageField(upload_to="gallery/thumbnails/", blank=True, null=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    year = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="gallery_uploads"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-created_at"]
        indexes = [models.Index(fields=["year"]), models.Index(fields=["media_type"])]

    def __str__(self):
        return f"{self.title} ({self.year})"

class FAQ(models.Model):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]
        indexes = [models.Index(fields=["order"]), models.Index(fields=["is_published"])]

    def __str__(self):
        return self.question


class TempleInfo(models.Model):
    """Singleton — one row holds the public temple profile."""
    name = models.CharField(max_length=200, blank=True, default="")
    established_year = models.CharField(max_length=10, blank=True, default="")
    registration = models.CharField(max_length=255, blank=True, default="")
    tagline = models.CharField(max_length=255, blank=True, default="")
    about = models.TextField(blank=True, default="")
    address = models.CharField(max_length=500, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    alt_phone = models.CharField(max_length=30, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.CharField(max_length=255, blank=True, default="")
    profile_photo = models.ImageField(upload_to="temple/", blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or "Temple Info"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj