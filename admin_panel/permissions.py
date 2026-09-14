from rest_framework.permissions import BasePermission
class IsBackeyAdmin(BasePermission):
    message="هذه الواجهة مخصصة لإدارة Backey فقط."
    def has_permission(self,request,view):
        u=getattr(request,"user",None)
        return bool(u and getattr(u,"is_authenticated",False) and (getattr(u,"is_staff",False) or getattr(u,"is_superuser",False)))
