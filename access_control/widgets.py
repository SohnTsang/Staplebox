from django.forms import CheckboxSelectMultiple, CheckboxInput
from django.utils.html import format_html
from django.utils.safestring import mark_safe

class ClickableListWidget(CheckboxSelectMultiple):
    template_name = 'access_control/widgets/clickable_list_widget.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        # Add extra context to render in the template as needed
        return option

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['class'] = 'list-group'
        return super().render(name, value, attrs, renderer)