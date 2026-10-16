from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *
class UserAdmin(BaseUserAdmin):
    fieldsets=BaseUserAdmin.fieldsets + (('EPMS access',{'fields':('role','company','must_change_password')}),)
    add_fieldsets=BaseUserAdmin.add_fieldsets + (('EPMS access',{'fields':('email','role','company')}),)
    def save_model(self,request,obj,form,change):
        old=User.objects.filter(pk=obj.pk).values_list('role',flat=True).first() if change else None
        super().save_model(request,obj,form,change)
        if not change or old!=obj.role:AuditLog.objects.create(user=request.user,company=obj.company,action=f'Changed user role {obj.username} to {obj.role}',module='Authentication',ip_address=request.META.get('REMOTE_ADDR'))
admin.site.register(User,UserAdmin)
for model in [Company,Employee,Department,Shift,ShiftAssignment,Attendance,LeaveRequest,WFHRequest,SalaryStructure,Payroll,Holiday,Announcement,Notification,Document,AIChat,PasswordOTP,OvertimeRequest,LeavePolicy]: admin.site.register(model)
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display=('user','module','action','created_at','ip_address')
    readonly_fields=('user','module','action','created_at','ip_address')
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
