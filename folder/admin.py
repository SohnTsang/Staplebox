from django.contrib import admin
from .models import Folder
from .utils import handle_item_action

class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_bin', 'bin_expires_at']
    actions = ['move_selected_to_bin', 'restore_selected', 'delete_permanently']

    def move_selected_to_bin(self, request, queryset):
        bin_folder = Folder.objects.get(name="Bin", is_bin=True)  # Adjust based on actual bin logic
        for item in queryset:
            handle_item_action("move_to_bin", item, bin_folder=bin_folder)

    def restore_selected(self, request, queryset):
        for item in queryset:
            original_folder = item.parent  # Adjust based on your logic
            handle_item_action("restore", item, original_folder=original_folder)

    def delete_permanently(self, request, queryset):
        for item in queryset:
            handle_item_action("delete", item)

admin.site.register(Folder, FolderAdmin)
