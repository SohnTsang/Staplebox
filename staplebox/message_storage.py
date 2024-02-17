from django.contrib.messages.storage.fallback import FallbackStorage

class FilteredMessagesStorage(FallbackStorage):
    def add(self, level, message, extra_tags=''):
        # Filter out Allauth's login and logout success messages
        if 'Successfully signed in' in message or 'You have signed out' in message:
            return
        super().add(level, message, extra_tags)