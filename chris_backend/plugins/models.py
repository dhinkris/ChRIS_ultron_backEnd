
import os

from django.db import models
from django.conf import settings

import django_filters
from rest_framework.filters import FilterSet

from feeds.models import Feed, FeedFile


# API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values")]

# table of equivalence between front-end types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path'}

PLUGIN_TYPE_CHOICES = [("ds", "Data plugin"), ("fs", "Filesystem plugin")]

STATUS_TYPES = ['started', 'running-on-remote', 'finished-on-remote']

class Plugin(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    dock_image = models.CharField(max_length=500)
    type = models.CharField(choices=PLUGIN_TYPE_CHOICES, default='ds', max_length=4)

    class Meta:
        ordering = ('type',)

    def __str__(self):
        return self.name

    def get_plugin_parameter_names(self):
        """
        Custom method to get the list of plugin parameter names.
        """
        params = self.parameters.all()
        return [param.name for param in params]
    

class PluginFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(name="creation_date", lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(name="creation_date", lookup_expr='lte')
    
    class Meta:
        model = Plugin
        fields = ['name', 'dock_image', 'type', 'min_creation_date', 'max_creation_date']


class PluginParameter(models.Model):
    name = models.CharField(max_length=100)
    optional = models.BooleanField(default=True)
    default = models.CharField(max_length=200, blank=True)
    type = models.CharField(choices=TYPE_CHOICES, default='string', max_length=10)
    help = models.TextField(blank=True)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE,
                               related_name='parameters')
    
    class Meta:
        ordering = ('plugin',)

    def __str__(self):
        return self.name
    

class PluginInstance(models.Model):
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default=STATUS_TYPES[0])
    previous = models.ForeignKey("self", on_delete=models.CASCADE, null=True,
                                 related_name='next')
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, related_name='instances')
    owner = models.ForeignKey('auth.User')
    
    class Meta:
        ordering = ('start_date',)

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        """
        Overriden to save a new feed to the DB the first time the instance is saved.
        """
        super(PluginInstance, self).save(*args, **kwargs)
        if not hasattr(self, 'feed') and self.plugin.type=='fs':
            self._save_feed()
            
    def _save_feed(self):
        """
        Custom method to create and save a new feed to the DB.
        """
        feed = Feed()
        feed.plugin_inst = self;
        feed.save()
        feed.name = self.plugin.name
        feed.owner = [self.owner]
        feed.save()

    def get_root_instance(self):
        """
        Custom method to return the root plugin instance for this plugin instance.
        """
        current = self
        while not current.plugin.type == 'fs':
            current = current.previous
        return current
            
    def get_output_path(self):
        """
        Custom method to get the output directory for files generated by
        the plugin instance object.
        """
        # 'fs' plugins will output files to:
        # MEDIA_ROOT/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        # 'ds' plugins will output files to:
        # MEDIA_ROOT/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        current = self
        path = '/{0}_{1}/data'.format(current.plugin.name, current.id)
        while not current.plugin.type == 'fs':
            current = current.previous
            path = '/{0}_{1}'.format(current.plugin.name, current.id) + path
        root = settings.MEDIA_ROOT
        username = self.owner.username
        output_path = '{0}/{1}/feed_{2}'.format(root, username, current.feed.id) + path
        if not os.path.isdir(output_path):
            os.makedirs(output_path)
        return output_path

    def register_output_files(self):
        """
        Custom method to register files generated by the plugin instance object
        with the REST API.
        """
        fileCount = 0
        root_instance = self.get_root_instance()
        feed = root_instance.feed
        output_path = self.get_output_path()
        for (dirpath, dirnames, filenames) in os.walk(output_path):
            for name in filenames:
                feedfile = FeedFile(plugin_inst=self, feed=feed)
                feedfile.fname.name = os.path.join(dirpath, name)
                feedfile.save()
                fileCount+=1
        return fileCount


class PluginInstanceFilter(FilterSet):
    min_start_date = django_filters.DateFilter(name="start_date", lookup_expr='gte')
    max_start_date = django_filters.DateFilter(name="start_date", lookup_expr='lte')
    min_end_date = django_filters.DateFilter(name="end_date", lookup_expr='gte')
    max_end_date = django_filters.DateFilter(name="end_date", lookup_expr='lte')
    root_id = django_filters.CharFilter(method='filter_by_root_id')

    def filter_by_root_id(self, queryset, name, value):
        """
        Custom method to return the plugin instances in a queryset with a common root
        plugin instance.
        """
        filtered_queryset = []
        root_queryset = queryset.filter(pk=value)
        # check whether the root id value is in the DB 
        if not root_queryset.exists():
            return root_queryset
        queue = [root_queryset[0]]
        while len(queue) > 0:
            visited = queue.pop()
            queue.extend(list(visited.next.all()))
            filtered_queryset.append(visited)
        return filtered_queryset     

    class Meta:
        model = PluginInstance
        fields = ['root_id', 'status', 'previous_id', 'min_start_date', 'max_start_date',
                  'min_end_date', 'max_end_date']
        
        
class StringParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='string_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='string_inst')

    def __str__(self):
        return self.value
    
    
class IntParameter(models.Model):
    value = models.IntegerField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='int_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='int_inst')

    def __str__(self):
        return str(self.value)
    

class FloatParameter(models.Model):
    value = models.FloatField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='float_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='float_inst')

    def __str__(self):
        return str(self.value)


class BoolParameter(models.Model):
    value = models.BooleanField(default=False, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='bool_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='bool_inst')

    def __str__(self):
        return str(self.value)


class PathParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='path_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='path_inst')

    def __str__(self):
        return self.value



