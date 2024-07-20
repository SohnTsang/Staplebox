from django import template
from ..utils import get_file_type_icon

register = template.Library()

@register.filter(name='file_icon')
def file_icon(file_name):
    return get_file_type_icon(file_name)