from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import *
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model=Company
        fields=['id','name','created_at']
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['id','username','email','first_name','last_name','role','company']
class EmployeeSerializer(serializers.ModelSerializer):
    user=UserSerializer(read_only=True)
    department_name=serializers.CharField(source='department.name',read_only=True)
    company_name=serializers.CharField(source='company.name',read_only=True)
    email=serializers.EmailField(write_only=True,required=False)
    password=serializers.CharField(write_only=True,required=False)
    class Meta:
        model=Employee
        fields='__all__'
        read_only_fields=['company']
    def create(self,data):
        email=data.pop('email'); password=data.pop('password','Welcome123!'); code=data['code']; first=data['first_name']; last=data['last_name']
        user=User.objects.create_user(username=code,email=email,password=password,first_name=first,last_name=last,role='EMPLOYEE')
        return Employee.objects.create(user=user,**data)
class AttendanceSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source='employee.__str__',read_only=True)
    class Meta:
        model=Attendance
        fields='__all__'
        read_only_fields=[]
class LeaveSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source='employee.__str__',read_only=True)
    class Meta:
        model=LeaveRequest
        fields='__all__'
        read_only_fields=['employee','status','comment','reviewed_by','total_days']
class WFHSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source='employee.__str__',read_only=True)
    class Meta:
        model=WFHRequest
        fields='__all__'
        read_only_fields=['employee','status','comment','reviewed_by']
class PayrollSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source='employee.__str__',read_only=True)
    employee_code=serializers.CharField(source='employee.code',read_only=True)
    class Meta:
        model=Payroll
        fields='__all__'
class SimpleSerializer(serializers.ModelSerializer):
    class Meta:
        fields='__all__'
class AnnouncementSerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta):
        model=Announcement
        read_only_fields=['author','company']
class HolidaySerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta): model=Holiday; read_only_fields=['company']
class DepartmentSerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta): model=Department; read_only_fields=['company']
class ShiftSerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta): model=Shift; read_only_fields=['company']
class SalarySerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta): model=SalaryStructure
class DocumentSerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta):
        model=Document
        read_only_fields=['employee','uploaded_at','verified']
class NotificationSerializer(SimpleSerializer):
    class Meta(SimpleSerializer.Meta):
        model=Notification
        read_only_fields=['user','created_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name=serializers.CharField(source='sender.get_full_name',read_only=True)
    recipient_name=serializers.CharField(source='recipient.get_full_name',read_only=True)
    class Meta:
        model=ChatMessage
        fields=['id','sender','sender_name','recipient','recipient_name','body','created_at','read_at']
        read_only_fields=['sender','sender_name','recipient_name','created_at','read_at']

class LoginSerializer(TokenObtainPairSerializer):
    def validate(self,attrs):
        ident=attrs.get('username','')
        user=User.objects.filter(Q(username__iexact=ident)|Q(email__iexact=ident)).first()
        generic='Unable to log in with provided credentials.'
        if user and not user.company_id:raise AuthenticationFailed(generic)
        if user and user.locked_until and user.locked_until>timezone.now():
            raise AuthenticationFailed(generic)
        if user and '@' in ident:
            attrs['username']=user.username
        try:
            result=super().validate(attrs)
            user.failed_logins=0; user.locked_until=None; user.save(update_fields=['failed_logins','locked_until'])
            return result
        except AuthenticationFailed:
            if user:
                user.failed_logins+=1
                if user.failed_logins>=5:
                    user.failed_logins=0; user.locked_until=timezone.now()+timedelta(minutes=15)
                user.save(update_fields=['failed_logins','locked_until'])
            raise AuthenticationFailed(generic)

class OvertimeSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source='employee.__str__',read_only=True)
    class Meta:
        model=OvertimeRequest; fields='__all__'; read_only_fields=['employee','status','reviewed_by']
class AuditSerializer(serializers.ModelSerializer):
    username=serializers.CharField(source='user.username',read_only=True)
    class Meta:
        model=AuditLog; fields='__all__'
class AIChatSerializer(serializers.ModelSerializer):
    class Meta:
        model=AIChat; fields=['id','question','answer','created_at']
class LeavePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model=LeavePolicy; fields='__all__'; read_only_fields=['company']
