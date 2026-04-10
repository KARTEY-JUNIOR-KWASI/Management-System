from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add_str(value, arg):
    """Concatenates the value and the argument as strings."""
    return str(value) + str(arg)
