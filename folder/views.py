from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Folder
from .forms import FolderForm
from products.models import Product
from .models import Folder
from django.http import JsonResponse
from django.contrib import messages  # Optional: For user feedback
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django import forms
from django.utils import timezone
from .utils import handle_item_action, clean_bins
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import FolderSerializer
from rest_framework.parsers import JSONParser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging

logger = logging.getLogger(__name__)

@login_required
def folder_create(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    
    if product.user != request.user:
        messages.error(request, "You are not authorized to perform this action")
        return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}))


    root_folder, created = Folder.objects.get_or_create(
        name="Root", 
        product=product, 
        defaults={'is_root': True, 'parent': None}
    )


    if not created:
        root_folder.is_root = True
        root_folder.save()

    if request.method == 'POST':
        if request.content_type == 'application/json':
            data = JSONParser().parse(request)
            data['product'] = product.id
            data['created_by'] = request.user.id

            parent_id = data.get('parent_id')
            if parent_id:
                parent_folder = get_object_or_404(Folder, id=parent_id)
                data['parent'] = parent_folder.id
            else:
                data['parent'] = root_folder.id

            serializer = FolderSerializer(data=data)
            if serializer.is_valid():
                folder = serializer.save()
                print(f"Folder Created: {folder.name}, ID: {folder.id}, Parent ID: {folder.parent_id} via JSON")  # Debug print

                return JsonResponse({'success': True, 'folder_id': folder.id}, status=201)
            else:
                print("Validation Failed:", serializer.errors)
                return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
        else:
            form = FolderForm(request.POST)
            if form.is_valid():
                folder = form.save(commit=False)
                folder.product = product
                folder.created_by = request.user

                parent_id = request.POST.get('parent_id')
                if parent_id:
                    folder.parent_id = parent_id
                else:
                    folder.parent = root_folder

                folder.save()

                return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder.parent_id if folder.parent_id else ''}), status=303)

            else:
                messages.error(request, 'Error creating folder.')

    return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}), status=303)


@login_required
@require_http_methods(["GET", "POST"])
def edit_folder(request, product_id, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
    parent_folder_id = folder.parent_id

    if request.method == 'POST':
        if request.content_type == 'application/json':
            print("JSON")
            data = JSONParser().parse(request)
            serializer = FolderSerializer(folder, data=data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'success': True, 'message': 'Folder updated'}, status=200)
            else:
                return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
        else:
            print("Non-JSOn")
            form = FolderForm(request.POST, instance=folder, use_required_attribute=False)
            form.fields['parent'].widget = forms.HiddenInput()  # Ensure parent field remains hidden
            if form.is_valid():
                form.save()
                return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': parent_folder_id}))
    
    else:
        form = FolderForm(instance=folder, use_required_attribute=False)
        form.fields['parent'].widget = forms.HiddenInput()

    return render(request, 'folders/edit_folder.html', {'form': form, 'product_id': product_id, 'folder_id': folder_id})


@login_required
def ajax_get_folder_details(request, product_id, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
    data = {
        'name': folder.name,
        'parent_id': folder.parent_id if folder.parent else '',
    }
    return JsonResponse(data)


class DeleteFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        folder_ids = request.data.get('folder_ids', [])

        folders = Folder.objects.filter(id__in=folder_ids)

        if not folders.exists():
            return Response({"detail": "Folders not found."}, status=status.HTTP_404_NOT_FOUND)

        for folder in folders:
            if folder.product.user != request.user:
                return Response({"detail": "You do not have permission to delete this folder."}, status=status.HTTP_403_FORBIDDEN)

            folder.delete()

        return Response({'detail': 'Items deleted'}, status=status.HTTP_200_OK)

    

@login_required
def move_to_bin_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    parent_id = folder.parent_id
    bin_folder = Folder.objects.get_or_create(name="Bin", product=folder.product, is_bin=True)[0]  # Ensure a bin exists
    handle_item_action("move_to_bin", folder, bin_folder=bin_folder)
    clean_bins()
    return redirect('products:product_explorer_folder', product_id=folder.product.id, folder_id=parent_id if folder.parent else '')


@login_required
def restore_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    handle_item_action("restore", folder)
    return redirect('products:product_explorer_bin', product_id=folder.product.id)