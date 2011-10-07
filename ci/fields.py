from django.db import models
from django import forms
from django.core.files.base import ContentFile


class StringListField(models.CharField):
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if value and not isinstance(value, list):
            value = filter(None, [s.strip() for s in value.split(',')])
        return value

    def get_prep_value(self, value):
        if value:
            value = ', '.join(value)
        return value

    def formfield(self, **kwargs):
        kwargs['form_class'] = StringListFormField
        return super(StringListField, self).formfield(**kwargs)

class StringListFormField(forms.CharField):
    def prepare_value(self, value):
        if value:
            value = ', '.join(value)
        return value


class NamedFieldFile(models.FileField.attr_class):
    def save_named(self, content, **kwargs):
        if isinstance(content, basestring):
            content = ContentFile(content)
        return super(NamedFieldFile, self).save(self.field.filename, content, **kwargs)

class NamedFileField(models.FileField):
    attr_class = NamedFieldFile

    def __init__(self, filename, **kwargs):
        self.filename = filename
        super(NamedFileField, self).__init__(**kwargs)
