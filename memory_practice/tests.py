import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from .models import MemoryLesson,MemoryQuestion,MemoryAttempt
from .services import validate_grade
from .ai import PracticeError

class MemoryTests(TestCase):
    def setUp(self):
        cache.clear();self.user=get_user_model().objects.create_user(username='learner');self.other=get_user_model().objects.create_user(username='other')
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.lesson=MemoryLesson.objects.create(tag='test',title='درس تجريبي',content={'bac_ideas':[{'id':'idea1','title':'تعريف','prompt':'عرف المفهوم','model_answer':'معنى المفهوم'}],'axes':[]})
        self.q=MemoryQuestion.objects.create(user=self.user,lesson=self.lesson,idea_id='idea1',verb='define',text='عرف المفهوم وحدد أثره.',rubric=[{'id':'c1','criterion':'التعريف','points':1},{'id':'c2','criterion':'الأثر','points':1}],model_answer='تعريف موجز وأثره.',fingerprint='abc')
    def result(self):return {'items':[{'criterion_id':'c1','credit':1,'quote':'التعريف','feedback':'التعريف حاضر.'},{'criterion_id':'c2','credit':0,'quote':'','feedback':'ينقص الأثر.'}],'summary':'أضف الأثر لتكمل الإجابة.'}
    def test_no_model_answer_before_submission(self):
        r=self.client.get(f'/questions/{self.q.pk}/');self.assertEqual(r.status_code,200)
        self.assertNotIn('rubric',r.data);self.assertNotIn('model_answer',r.data);self.assertEqual(r.data['attempts'],[])
    def test_other_user_cannot_read_or_answer(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/questions/{self.q.pk}/').status_code,404)
        self.assertEqual(self.client.post(f'/questions/{self.q.pk}/answer/',{'answer':'نص','request_key':str(uuid.uuid4())}).status_code,404)
    @patch('memory_practice.services.ask')
    def test_grade_and_idempotency(self,ask):
        ask.return_value=self.result();body={'answer':'التعريف صحيح','request_key':str(uuid.uuid4())}
        a=self.client.post(f'/questions/{self.q.pk}/answer/',body);b=self.client.post(f'/questions/{self.q.pk}/answer/',body)
        self.assertEqual(a.status_code,200);self.assertEqual(a.data['result']['score'],1);self.assertEqual(a.data['result']['missing'],['الأثر'])
        self.assertEqual(a.data['id'],b.data['id']);self.assertEqual(ask.call_count,1)
    def test_fake_quote_rejected(self):
        data=self.result();data['items'][0]['quote']='كلام لم يكتبه الطالب'
        with self.assertRaises(PracticeError):validate_grade(data,self.q,'التعريف')
    def test_out_of_range_credit_rejected(self):
        data=self.result();data['items'][0]['credit']=10
        with self.assertRaises(PracticeError):validate_grade(data,self.q,'التعريف')
    def test_duplicate_criterion_rejected(self):
        data=self.result();data['items'][1]['criterion_id']='c1'
        with self.assertRaises(PracticeError):validate_grade(data,self.q,'التعريف')
    @patch('memory_practice.services.ask')
    def test_empty_answer_no_ai(self,ask):
        r=self.client.post(f'/questions/{self.q.pk}/answer/',{'answer':'  ','request_key':str(uuid.uuid4())});self.assertEqual(r.status_code,400);ask.assert_not_called()
    @patch('memory_practice.services.ask')
    def test_failed_attempt_can_resume(self,ask):
        body={'answer':'التعريف صحيح','request_key':str(uuid.uuid4())};ask.side_effect=PracticeError('مؤقت',503)
        self.assertEqual(self.client.post(f'/questions/{self.q.pk}/answer/',body).status_code,503)
        self.assertEqual(MemoryAttempt.objects.get().status,'failed');ask.side_effect=None;ask.return_value=self.result()
        self.assertEqual(self.client.post(f'/questions/{self.q.pk}/answer/',body).status_code,200)
    @patch('memory_practice.services.ask')
    def test_question_generation(self,ask):
        ask.return_value={'text':'عرف المفهوم في عبارة موجزة.','rubric':[{'criterion':'المعنى','source_ref':'idea'},{'criterion':'الدلالة','source_ref':'idea'}],'model_answer':'صياغة موجزة.'}
        with patch('memory_practice.catalog.snapshot',return_value=self.lesson):
            r=self.client.post('/generate/',{'axis_id':17,'verb':'define'})
        self.assertEqual(r.status_code,201);self.assertNotIn('rubric',r.data)
        self.assertEqual(MemoryQuestion.objects.count(),2)
    def test_unauthenticated_blocked(self):
        self.client=APIClient();self.assertIn(self.client.get('/lessons/').status_code,(401,403))
