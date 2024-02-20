from django.shortcuts import render
from .models import Partnership
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

@login_required
def partner_list_view(request):
    user = request.user
    if user.userprofile.role == 'exporter':
        partnerships = Partnership.objects.filter(exporter=user)
    else:  # Assuming the only other role is 'importer'
        partnerships = Partnership.objects.filter(importer=user)
    context = {'partnerships': partnerships}
    return render(request, 'partners/partner_list.html', context)


@login_required
@require_POST
def delete_partner(request, partner_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=403)

    try:
        partner = get_object_or_404(Partnership, id=partner_id, exporter=request.user)
        partner.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        # Log the error for debugging
        print(f"Error deleting partner: {e}")
        return JsonResponse({'success': False, 'error': 'Internal Server Error'}, status=500)
