from django.conf import settings
from django.db import models

class MemoryLesson(models.Model):
    tag=models.CharField(max_length=160,unique=True)
    title=models.CharField(max_length=255)
    order=models.PositiveIntegerField(default=0)
    branches=models.JSONField(default=list)
    content=models.JSONField(default=dict)
    bac_references=models.JSONField(default=list)
    is_active=models.BooleanField(default=True)
    class Meta: ordering=['order','id']

class MemoryQuestion(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    lesson=models.ForeignKey(MemoryLesson,on_delete=models.PROTECT)
    idea_id=models.CharField(max_length=120)
    verb=models.CharField(max_length=24)
    text=models.TextField()
    evidence=models.JSONField(default=dict)
    rubric=models.JSONField(default=list)
    model_answer=models.TextField()
    source_snapshot=models.JSONField(default=dict)
    fingerprint=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['user','lesson','fingerprint'],name='memory_unique_user_question')]

class MemoryAttempt(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    question=models.ForeignKey(MemoryQuestion,on_delete=models.CASCADE,related_name='attempts')
    request_key=models.UUIDField()
    answer=models.TextField()
    result=models.JSONField(default=dict)
    status=models.CharField(max_length=16,default='pending')
    lease_token=models.CharField(max_length=40,default='')
    updated_at=models.DateTimeField(auto_now=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['created_at']
        constraints=[models.UniqueConstraint(fields=['user','question','request_key'],name='memory_attempt_request_unique')]

class MemoryExercise(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    chapter_id=models.PositiveIntegerField(db_index=True)
    branch_code=models.CharField(max_length=100,blank=True,default='')
    title=models.CharField(max_length=255)
    question_ids=models.JSONField(default=list)
    reference_id=models.PositiveIntegerField(null=True,blank=True)
    request_key=models.UUIDField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['user','request_key'],name='memory_exercise_request_unique')]
