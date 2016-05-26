from django.db import models


# Create your models here.

class Feed(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=True, default='')
    owner = models.ManyToManyField('auth.User', related_name='feed')
    
    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super(Feed, self).save(*args, **kwargs)
        # save a new note the first time the feed is saved
        if not hasattr(self, 'note'):
            note = Note()
            note.feed = self;
            note.save()        
        

class Note(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.OneToOneField(Feed, on_delete=models.CASCADE, related_name='note')
    
    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=20)
    feed = models.ManyToManyField(Feed, related_name='tags')
    owner = models.ForeignKey('auth.User')

    def __str__(self):
        return self.name


class Comment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, default='')
    content = models.TextField(blank=True, default='')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='comments')
    owner = models.ForeignKey('auth.User')

    class Meta:
        ordering = ('creation_date',)

    def __str__(self):
        return self.title


def user_directory_path(instance, filename):
    # file will be stored to:
    # MEDIA_ROOT/<username>/<year>_<month>_<day>/feed_<id><filename>
    #import pdb; pdb.set_trace()
    username = instance.feed.user.username
    feed_id = instance.feed.id
    t = timezone.now()
    return '{0}/{1}_{2}_{3}/feed_{4}/{5}'.format(username, t.year,
                                                 t.month, t.day, feed_id, filename)


class FeedFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(max_length=200)
    feed = models.ManyToManyField(Feed, related_name='files')

    def __str__(self):
        return self.file.name
    

