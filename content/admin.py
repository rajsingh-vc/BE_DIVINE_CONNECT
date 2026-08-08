from django.contrib import admin

from .models import ContentPage, Announcement
from .models import ContentPage, Announcement, GalleryItem

from django.contrib import admin
from .models import TempleInfo
from .models import NewsPost


from .models import VideoItem

@admin.register(VideoItem)
class VideoItemAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "uploaded_by", "created_at")
    list_filter = ("source_type",)
    search_fields = ("title", "description")
    readonly_fields = ("youtube_video_id", "created_at")

@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "slug")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "sent_by", "sent_at")
    list_filter = ("type",)
    search_fields = ("title", "description")
    readonly_fields = ("sent_at",)




@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "year", "uploaded_by", "created_at")
    list_filter = ("media_type", "year")
    search_fields = ("title", "description")
    readonly_fields = ("created_at",)





@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "author", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(TempleInfo)
class TempleInfoAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_at")