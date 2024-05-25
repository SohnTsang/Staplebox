from django import template

register = template.Library()

@register.filter(name='custom_range')
def custom_range(value):
    """
    Creates a range of numbers from a string input that may include 1 to 3 integers.
    Usage:
        {% for i in '5'|custom_range %}  # Outputs range 0 to 5
        {% for i in '1,5'|custom_range %}  # Outputs range 1 to 5
        {% for i in '1,10,2'|custom_range %}  # Outputs range 1 to 10 stepping by 2
    """
    parts = value.split(',')
    parts = [int(x) for x in parts]  # Convert parts to integers
    return range(*parts)


@register.filter
def get_width(index):
    # Define specific widths based on index
    widths = {
        0: "90%",
        1: "60%",
        2: "70%",
        3: "90%",
        4: "50%",
        5: "80%"
    }
    return widths.get(index, "100%")  # Default width if index is out of range