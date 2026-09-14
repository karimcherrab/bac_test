from rest_framework import serializers
from accounts.models import Student
from course.models import Chapter,Subject
from payments.models import Pack,Purchase
class StudentAdminSerializer(serializers.ModelSerializer):
    branch=serializers.SerializerMethodField();purchases_count=serializers.IntegerField(read_only=True);accesses_count=serializers.IntegerField(read_only=True)
    class Meta:model=Student;fields=["id","username","email","branch","is_active","email_verified_at","created_at","purchases_count","accesses_count"]
    def get_branch(self,o):return {"id":o.branch_id,"code":o.branch.code,"name":o.branch.name} if o.branch_id else None
class AdminPackSerializer(serializers.ModelSerializer):
    chapter_id=serializers.PrimaryKeyRelatedField(source="chapter",queryset=Chapter.objects.all(),allow_null=True,required=False)
    subject_id=serializers.PrimaryKeyRelatedField(source="subject",queryset=Subject.objects.all(),allow_null=True,required=False)
    target_id=serializers.SerializerMethodField();target_title=serializers.SerializerMethodField()
    class Meta:model=Pack;fields=["id","pack_type","name","description","price_dzd","subject_id","chapter_id","target_id","target_title","is_active","metadata","created_at","updated_at"];read_only_fields=["id","target_id","target_title","created_at","updated_at"]
    def validate(self,a):
        i=self.instance;t=a.get("pack_type",getattr(i,"pack_type",None));c=a.get("chapter",getattr(i,"chapter",None));s=a.get("subject",getattr(i,"subject",None))
        if t==Pack.PackType.CHAPTER:
            if c is None:raise serializers.ValidationError({"chapter_id":"اختر الوحدة."})
            if s is not None:raise serializers.ValidationError({"subject_id":"باقة الوحدة لا تستعمل subject_id."})
        elif t==Pack.PackType.SUBJECT:
            if s is None:raise serializers.ValidationError({"subject_id":"اختر المادة."})
            if c is not None:raise serializers.ValidationError({"chapter_id":"باقة المادة لا تستعمل chapter_id."})
        return a
    def get_target_id(self,o):return o.subject_id if o.pack_type==Pack.PackType.SUBJECT else o.chapter_id
    def get_target_title(self,o):return o.target_title
class AdminPurchaseSerializer(serializers.ModelSerializer):
    student=serializers.SerializerMethodField();pack=serializers.SerializerMethodField()
    class Meta:model=Purchase;fields=["id","student","pack","amount_dzd","currency","status","payment_method","chargily_checkout_id","customer_email","paid_at","created_at","updated_at"]
    def get_student(self,o):return {"id":o.student_id,"username":o.student.username,"email":o.student.email}
    def get_pack(self,o):return {"id":o.pack_id,"name":o.pack.name,"pack_type":o.pack.pack_type,"target_title":o.pack.target_title}
