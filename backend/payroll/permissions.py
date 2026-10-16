from rest_framework.permissions import BasePermission, SAFE_METHODS
class IsCompanyUser(BasePermission):
 def has_permission(self,request,view):
  user=request.user
  if not user or not user.is_authenticated or not user.company_id:return False
  if user.must_change_password:
   return request.path in ['/api/auth/me/','/api/auth/change-password/','/api/auth/logout/']
  return True
class IsAdminOrSelf(BasePermission):
 def has_permission(self,request,view): return IsCompanyUser().has_permission(request,view)
 def has_object_permission(self,request,view,obj):
  if request.user.role=='ADMIN' or request.user.is_superuser: return True
  employee=getattr(request.user,'employee',None)
  return obj==employee or getattr(obj,'employee_id',None)==getattr(employee,'id',None) or getattr(obj,'user_id',None)==request.user.id
class IsAdminRole(BasePermission):
 def has_permission(self,request,view): return bool(IsCompanyUser().has_permission(request,view) and (request.user.role=='ADMIN' or request.user.is_superuser))
class IsAdminOrReadOnly(BasePermission):
 def has_permission(self,request,view): return bool(IsCompanyUser().has_permission(request,view) and (request.method in SAFE_METHODS or request.user.role=='ADMIN' or request.user.is_superuser))
