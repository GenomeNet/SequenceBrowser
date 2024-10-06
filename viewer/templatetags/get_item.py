from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def combine_methods(method1, method2):
    return f"{method1}__{method2}"