from .models import UserActivity

def log_user_activity(user, action, activity_type, item_name=None):
    description = action
    if item_name:
        description += f" - {item_name}"
    
    UserActivity.objects.create(
        user=user,
        action=description,
        activity_type=activity_type
    )