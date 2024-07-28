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
from django.core.signing import Signer, BadSignature
import logging

signer = Signer()


logger = logging.getLogger(__name__)

@login_required
def folder_create(request, product_uuid):
    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
        product = get_object_or_404(Product, uuid=unsigned_product_uuid)
    except BadSignature:
        messages.error(request, "Invalid product ID.")
        return redirect('products:product_list')

    if product.user != request.user:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect(reverse('products:product_explorer', kwargs={'product_uuid': product_uuid}))

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
            data['product'] = product.uuid
            data['created_by'] = request.user.id

            parent_id = data.get('parent_id')
            if parent_id:
                try:
                    unsigned_parent_id = signer.unsign(parent_id)
                    parent_folder = get_object_or_404(Folder, uuid=unsigned_parent_id)
                    data['parent'] = parent_folder.uuid
                except BadSignature:
                    return JsonResponse({'success': False, 'errors': 'Invalid parent folder ID.'}, status=400)
            else:
                data['parent'] = root_folder.uuid

            serializer = FolderSerializer(data=data)
            if serializer.is_valid():
                folder = serializer.save()
                return JsonResponse({'success': True, 'folder_id': signer.sign(str(folder.uuid))}, status=201)
            else:
                return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
        else:
            form = FolderForm(request.POST)
            if form.is_valid():
                folder = form.save(commit=False)
                folder.product = product
                folder.created_by = request.user

                parent_id = request.POST.get('parent_id')
                if parent_id:
                    try:
                        unsigned_parent_id = signer.unsign(parent_id)
                        folder.parent = get_object_or_404(Folder, uuid=unsigned_parent_id)
                    except BadSignature:
                        messages.error(request, "Invalid parent folder ID.")
                        return redirect(reverse('products:product_explorer', kwargs={'product_uuid': product_uuid}))
                else:
                    folder.parent = root_folder

                folder.save()
                return redirect(reverse('products:product_explorer_folder', kwargs={'product_uuid': product_uuid, 'folder_uuid': folder.uuid}), status=303)
            else:
                messages.error(request, 'Error creating folder.')

    return redirect(reverse('products:product_explorer', kwargs={'product_uuid': product_uuid}), status=303)


@login_required
def get_folder_data(request):
    folder_id = request.GET.get('folder_id')
    product_id = request.GET.get('product_id')
    if folder_id is None or product_id is None:
        return JsonResponse({'error': 'Folder ID or Product ID is missing'}, status=400)

    return JsonResponse({'folder_id': folder_id, 'product_id': product_id})


@login_required
@require_http_methods(["GET", "POST"])
def edit_folder(request, product_uuid, folder_uuid):
    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
        unsigned_folder_uuid = signer.unsign(folder_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)
    
    # Set the session variables here when this view is first called
    if request.method == 'GET':
        request.session['folder_id'] = unsigned_folder_uuid
        request.session['product_id'] = unsigned_product_uuid

    folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid, product__uuid=unsigned_product_uuid)
    parent_folder_id = folder.parent_id

    if request.method == 'POST':
        if request.content_type == 'application/json':
            data = JSONParser().parse(request)
            serializer = FolderSerializer(folder, data=data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'success': True, 'message': 'Folder updated'}, status=200)
            else:
                return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)
        else:
            form = FolderForm(request.POST, instance=folder, use_required_attribute=False)
            form.fields['parent'].widget = forms.HiddenInput()
            if form.is_valid():
                form.save()
                return redirect(reverse('products:product_explorer_folder', kwargs={'product_uuid': product_uuid, 'folder_uuid': parent_folder_id}))
    
    else:
        form = FolderForm(instance=folder, use_required_attribute=False)
        form.fields['parent'].widget = forms.HiddenInput()

    return render(request, 'folders/edit_folder.html', {'form': form, 'product_uuid': product_uuid, 'folder_uuid': folder_uuid})

    

@login_required
def ajax_get_folder_details(request, product_uuid, folder_uuid):
    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
        unsigned_folder_uuid = signer.unsign(folder_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid, product__uuid=unsigned_product_uuid)
    data = {
        'name': folder.name,
        'parent_id': folder.parent_id if folder.parent else '',
    }
    return JsonResponse(data)


class DeleteFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        signed_folder_ids = request.data.get('folder_ids', [])
        folder_ids = []

        print(signed_folder_ids)
        # Unsign folder IDs
        for signed_id in signed_folder_ids:
            if signed_id:
                try:
                    unsigned_id = signer.unsign(signed_id)
                    folder_ids.append(unsigned_id)
                except BadSignature:
                    return Response({"detail": f"Invalid folder ID: {signed_id}"}, status=status.HTTP_400_BAD_REQUEST)

        if not folder_ids:
            return Response({"detail": "No valid folder IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        folders = Folder.objects.filter(uuid__in=folder_ids)

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
    return redirect('products:product_explorer_folder', product_id=folder.product.uuid, folder_id=parent_id if folder.parent else '')


@login_required
def restore_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    handle_item_action("restore", folder)
    return redirect('products:product_explorer_bin', product_uuid=folder.product.uuid)