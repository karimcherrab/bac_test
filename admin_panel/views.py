from django.contrib.auth import authenticate
from django.db.models import Count,Q,Sum
from django.db.models.functions import Coalesce
from rest_framework import status,viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import Student
from course.models import Subject
from payments.models import Pack,Purchase
from .permissions import IsBackeyAdmin
from .serializers import AdminPackSerializer,AdminPurchaseSerializer,StudentAdminSerializer
class AdminLoginView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        u=authenticate(request=request,username=str(request.data.get("username","")).strip(),password=str(request.data.get("password","")))
        if not u:return Response({"detail":"اسم المستخدم أو كلمة المرور غير صحيحة."},status=status.HTTP_401_UNAUTHORIZED)
        if not(getattr(u,"is_staff",False) or getattr(u,"is_superuser",False)):return Response({"detail":"هذا الحساب ليس حساب إدارة."},status=status.HTTP_403_FORBIDDEN)
        r=RefreshToken.for_user(u);return Response({"access":str(r.access_token),"refresh":str(r),"admin":{"id":u.pk,"username":getattr(u,"username","")}})
class AdminAPIView(APIView):authentication_classes=[JWTAuthentication];permission_classes=[IsBackeyAdmin]
class DashboardView(AdminAPIView):
    def get(self,request):
        rev=Purchase.objects.filter(status=Purchase.Status.PAID).aggregate(total=Coalesce(Sum("amount_dzd"),0))["total"]
        recent=Purchase.objects.select_related("student","pack","pack__chapter","pack__subject").order_by("-created_at")[:8]
        return Response({"revenue_paid":rev,"payments_count":Purchase.objects.count(),"pending_count":Purchase.objects.filter(status=Purchase.Status.PENDING).count(),"students_count":Student.objects.count(),"active_packs_count":Pack.objects.filter(is_active=True).count(),"recent_payments":AdminPurchaseSerializer(recent,many=True).data})
class PaymentsView(AdminAPIView):
    def get(self,request):
        q=Purchase.objects.select_related("student","pack","pack__chapter","pack__subject").order_by("-created_at");st=request.query_params.get("status");s=str(request.query_params.get("search","")).strip()
        if st:q=q.filter(status=st)
        if s:q=q.filter(Q(student__username__icontains=s)|Q(student__email__icontains=s)|Q(chargily_checkout_id__icontains=s)|Q(pack__name__icontains=s))
        d=AdminPurchaseSerializer(q[:500],many=True).data;return Response({"count":len(d),"results":d})
class StudentsView(AdminAPIView):
    def get(self,request):
        s=str(request.query_params.get("search","")).strip();q=Student.objects.select_related("branch").annotate(purchases_count=Count("purchases",distinct=True),accesses_count=Count("paid_accesses",distinct=True)).order_by("-created_at")
        if s:q=q.filter(Q(username__icontains=s)|Q(email__icontains=s))
        d=StudentAdminSerializer(q[:1000],many=True).data;return Response({"count":len(d),"results":d})
class CatalogView(AdminAPIView):
    def get(self,request):
        subs=Subject.objects.prefetch_related("chapters").order_by("name");sp={p.subject_id:p for p in Pack.objects.filter(pack_type=Pack.PackType.SUBJECT) if p.subject_id};cp={p.chapter_id:p for p in Pack.objects.filter(pack_type=Pack.PackType.CHAPTER) if p.chapter_id};out=[]
        for s in subs:
            p=sp.get(s.id);chs=[]
            for c in s.chapters.all():
                x=cp.get(c.id);chs.append({"id":c.id,"code":c.code,"title":c.title,"order":c.order,"is_active":c.is_active,"pack":{"id":x.id,"price_dzd":x.price_dzd,"is_active":x.is_active} if x else None})
            out.append({"id":s.id,"code":s.code,"name":s.name,"description":s.description,"pack":{"id":p.id,"price_dzd":p.price_dzd,"is_active":p.is_active} if p else None,"chapters":chs})
        return Response({"subjects":out})
class AdminPackViewSet(viewsets.ModelViewSet):
    authentication_classes=[JWTAuthentication];permission_classes=[IsBackeyAdmin];serializer_class=AdminPackSerializer;queryset=Pack.objects.select_related("subject","chapter","chapter__subject").all().order_by("-updated_at")
