def user_info(request):
    user_email = None
    user_name = None

    if request.user.is_authenticated:
        user_email = request.user.email
        user_name = user_email.split('@')[0]

    return {
        'user_email': user_email,
        'user_name': user_name,
    }