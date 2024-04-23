from django.utils import timezone
from .models import Folder
from documents.models import Document
from django.db import transaction


def move_to_bin(item, bin_folder):
    if isinstance(item, Document):
        item.original_folder = item.folder if not item.original_folder else item.original_folder
        item.folder = bin_folder
    elif isinstance(item, Folder):
        item.original_parent = item.parent if not item.original_parent else item.original_parent
        item.parent = bin_folder
    item.bin_expires_at = timezone.now() + timezone.timedelta(minutes=1)
    item.save()


def restore_item(item):
    if isinstance(item, Document):
        item.folder = item.original_folder if item.original_folder else item.folder
        item.original_folder = None
    elif isinstance(item, Folder):
        item.parent = item.original_parent if item.original_parent else item.parent
        item.original_parent = None
    item.bin_expires_at = None
    item.save()


def permanently_delete(item):
    item.delete()


# To handle both folders and documents dynamically, check the item's type:
def handle_item_action(action, item, **kwargs):
    if isinstance(item, Folder):
        if action == "move_to_bin":
            move_to_bin(item, kwargs['bin_folder'])
        elif action == "restore":
            restore_item(item)  # Don't pass kwargs['original_folder']
        elif action == "delete":
            permanently_delete(item)
    elif isinstance(item, Document):
        if action == "move_to_bin":
            move_to_bin(item, kwargs['bin_folder'])
        elif action == "restore":
            restore_item(item)  # Don't pass kwargs['original_folder']
        elif action == "delete":
            permanently_delete(item)


def clean_bins():
    bins = Folder.objects.filter(is_bin=True)
    with transaction.atomic():
        for bin in bins:
            # Cleaning expired folders
            expired_folders = bin.subfolders.filter(bin_expires_at__lte=timezone.now())
            expired_folders.delete()  # Deletes all expired subfolders

            # Cleaning expired documents
            expired_documents = Document.objects.filter(folder=bin, bin_expires_at__lte=timezone.now())
            expired_documents.delete()  # Deletes all expired documents