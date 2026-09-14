import logging
from django.shortcuts import get_object_or_404
from rest_framework import serializers,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from .models import MemoryLesson,MemoryQuestion
from . import catalog
from .services import new_question,grade,VERBS
from .ai import PracticeError
logger=logging.getLogger(__name__)

class MemoryThrottle(UserRateThrottle):rate='12/min'
class GenerateRequest(serializers.Serializer):
    axis_id=serializers.IntegerField(min_value=1)
    chapter_id=serializers.IntegerField(min_value=1,required=False)
    branch_code=serializers.CharField(max_length=100,required=False,allow_blank=True,default="")
    verb=serializers.ChoiceField(choices=['mixed',*VERBS],default='mixed')
class AnswerRequest(serializers.Serializer):
    answer=serializers.CharField(max_length=6000,allow_blank=False,trim_whitespace=True)
    request_key=serializers.UUIDField()

def attempt_payload(a):return {'id':a.pk,'answer':a.answer,'result':a.result,'created_at':a.created_at}
def question_payload(q):
    return {'id':q.pk,'lesson_id':q.lesson_id,'lesson_title':q.lesson.title,'verb':q.verb,'verb_label':VERBS[q.verb],
            'text':q.text,'evidence':q.evidence,'max_score':len(q.rubric),'created_at':q.created_at,
            'attempts':[attempt_payload(a) for a in q.attempts.filter(user=q.user,status='done').order_by('created_at')]}

class Base(APIView):
    permission_classes=[IsAuthenticated]
    throttle_classes=[MemoryThrottle]
    def handle_exception(self,exc):
        if isinstance(exc,PracticeError):return Response({'detail':str(exc)},status=exc.status)
        return super().handle_exception(exc)

class Context(Base):
    def get(self,request):
        return Response(catalog.chapter_context(request.query_params.get('chapter_id')))

class Lessons(Base):
    def get(self,request):
        chapter=request.query_params.get('chapter_id')
        if not chapter: raise serializers.ValidationError({'chapter_id':'حدد الوحدة.'})
        rows=[]
        for axis in catalog.axes(chapter,request.query_params.get('branch_code','')):
            key=catalog.subject_key(axis.chapter.subject)
            if key not in ('islamic','history'): continue
            content=catalog.normalize_content(axis.content,axis.title,key)
            rows.append({'id':axis.pk,'title':axis.title,'order':axis.order,
                         'subject_code':key,'idea_count':len(content['bac_ideas'])})
        return Response({'results':rows})
class Generate(Base):
    def post(self,request):
        s=GenerateRequest(data=request.data);s.is_valid(raise_exception=True)
        data=dict(s.validated_data);verb=data.pop('verb')
        lesson=catalog.snapshot(data.pop('axis_id'),branch=data.pop('branch_code'),**data)
        q=new_question(request.user,lesson,verb)
        return Response(question_payload(q),status=201)
class Detail(Base):
    def get(self,request,pk):
        return Response(question_payload(get_object_or_404(MemoryQuestion.objects.select_related('lesson'),pk=pk,user=request.user)))
class Answer(Base):
    def post(self,request,pk):
        s=AnswerRequest(data=request.data);s.is_valid(raise_exception=True)
        q=get_object_or_404(MemoryQuestion.objects.select_related('lesson'),pk=pk,user=request.user)
        result=grade(request.user,q,**s.validated_data)
        return Response(attempt_payload(result))
class History(Base):
    def get(self,request):
        qs=MemoryQuestion.objects.filter(user=request.user).select_related('lesson')
        value=request.query_params.get('axis_id')
        if value:
            if not value.isdigit():raise serializers.ValidationError({'lesson_id':'معرف غير صالح.'})
            qs=qs.filter(lesson__tag=f'db-axis-{int(value)}')
        return Response({'results':[question_payload(q) for q in qs[:20]]})

from .models import MemoryExercise
from .exercises import generate as generate_exercise

class ExerciseRequest(serializers.Serializer):
    chapter_id=serializers.IntegerField(min_value=1)
    branch_code=serializers.CharField(max_length=100,required=False,allow_blank=True,default='')
    request_key=serializers.UUIDField()

def exercise_payload(exercise):
    questions={q.pk:q for q in MemoryQuestion.objects.filter(user=exercise.user,pk__in=exercise.question_ids).select_related('lesson')}
    return {'id':exercise.pk,'chapter_id':exercise.chapter_id,'title':exercise.title,
            'reference_id':exercise.reference_id,'questions':[question_payload(questions[pk]) for pk in exercise.question_ids if pk in questions]}

class Exercises(Base):
    def post(self,request):
        s=ExerciseRequest(data=request.data);s.is_valid(raise_exception=True)
        d=s.validated_data
        exercise=generate_exercise(request.user,d['chapter_id'],d['branch_code'],d['request_key'])
        return Response(exercise_payload(exercise),status=201)
    def get(self,request):
        chapter=catalog.positive(request.query_params.get('chapter_id'),'الوحدة')
        branch=request.query_params.get('branch_code','')
        rows=MemoryExercise.objects.filter(user=request.user,chapter_id=chapter,branch_code=branch)[:10]
        return Response({'results':[exercise_payload(x) for x in rows]})
