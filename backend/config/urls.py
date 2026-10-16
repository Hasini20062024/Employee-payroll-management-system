from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from payroll.serializers import LoginSerializer
from payroll.views import *
class LoginView(TokenObtainPairView):
 serializer_class=LoginSerializer
router=DefaultRouter()
for name, view in [('employees',EmployeeViewSet),('attendance',AttendanceViewSet),('leave-requests',LeaveViewSet),('wfh-requests',WFHViewSet),('payroll',PayrollViewSet),('announcements',AnnouncementViewSet),('holidays',HolidayViewSet),('documents',DocumentViewSet),('departments',DepartmentViewSet),('shifts',ShiftViewSet),('salary-structures',SalaryViewSet),('notifications',NotificationViewSet),('messages',ChatMessageViewSet),('overtime',OvertimeViewSet),('shift-assignments',ShiftAssignmentViewSet),('audit-logs',AuditLogViewSet),('leave-policies',LeavePolicyViewSet),('ai/history',AIHistoryViewSet)]: router.register(name,view,basename=name)
urlpatterns=[path('',TemplateView.as_view(template_name='index.html'),name='home'),path('admin/',admin.site.urls),path('api/auth/token/',LoginView.as_view(),name='token_obtain_pair'),path('api/auth/register/',register_employee,name='register_employee'),path('api/auth/register-company/',register_company,name='register_company'),path('api/auth/change-password/',change_password,name='change_password'),path('api/auth/refresh/',TokenRefreshView.as_view(),name='token_refresh'),path('api/',include(router.urls)),path('api/dashboard/',dashboard),path('api/attendance-settings/',attendance_settings),path('api/ai/assistant/',assistant),path('api/ai/attendance-insights/',attendance_insights),path('api/payslips/<int:pk>/',payslip),path('api/auth/me/',me),path('api/auth/logout/',logout),path('api/auth/password-reset/request/',request_otp),path('api/auth/password-reset/verify/',verify_otp),path('api/search/',global_search),path('api/reports/export/',export_report),path('api/reports/bulk-payslips/',bulk_payslips)]
