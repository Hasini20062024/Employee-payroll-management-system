from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from datetime import time as datetime_time

class Company(models.Model):
 name=models.CharField(max_length=150,unique=True); created_at=models.DateTimeField(auto_now_add=True)
 def __str__(self): return self.name
class User(AbstractUser):
 class Role(models.TextChoices): ADMIN='ADMIN','Administrator'; EMPLOYEE='EMPLOYEE','Employee'
 email=models.EmailField(unique=True); role=models.CharField(max_length=12,choices=Role.choices,default=Role.EMPLOYEE); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.PROTECT,related_name='users'); must_change_password=models.BooleanField(default=False)
 failed_logins=models.PositiveSmallIntegerField(default=0); locked_until=models.DateTimeField(null=True,blank=True)
 REQUIRED_FIELDS=['email']
 def __str__(self): return self.get_full_name() or self.username
class Department(models.Model):
 name=models.CharField(max_length=100); description=models.TextField(blank=True); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='departments')
 class Meta: constraints=[models.UniqueConstraint(fields=['company','name'],name='unique_department_per_company')]
 def __str__(self): return self.name
class Employee(models.Model):
 user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='employee'); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.PROTECT,related_name='employees'); code=models.CharField(max_length=20,unique=True); first_name=models.CharField(max_length=50); last_name=models.CharField(max_length=50); department=models.ForeignKey(Department,null=True,blank=True,on_delete=models.SET_NULL); designation=models.CharField(max_length=100,blank=True); phone=models.CharField(max_length=20,blank=True); company_name=models.CharField(max_length=150,blank=True); address=models.TextField(blank=True); emergency_contact=models.CharField(max_length=20,blank=True); profile_photo=models.ImageField(upload_to='profiles/',null=True,blank=True); joining_date=models.DateField(default=timezone.localdate); employment_type=models.CharField(max_length=30,default='Full-time'); status=models.CharField(max_length=20,default='Active'); bank_name=models.CharField(max_length=100,blank=True); bank_account_number=models.CharField(max_length=40,blank=True); ifsc_code=models.CharField(max_length=20,blank=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta:
  constraints=[models.UniqueConstraint(fields=['bank_account_number'],condition=~Q(bank_account_number=''),name='unique_nonempty_bank_account')]
 def __str__(self): return f'{self.first_name} {self.last_name}'
class Shift(models.Model):
 name=models.CharField(max_length=50); start_time=models.TimeField(); end_time=models.TimeField(); grace_minutes=models.PositiveSmallIntegerField(default=10); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='shifts')
 class Meta: constraints=[models.UniqueConstraint(fields=['company','name'],name='unique_shift_per_company')]
class ShiftAssignment(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.CASCADE); shift=models.ForeignKey(Shift,on_delete=models.PROTECT); effective_from=models.DateField()
class AttendanceSettings(models.Model):
 company=models.OneToOneField(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='attendance_settings')
 office_latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
 office_longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
 radius_meters=models.PositiveIntegerField(default=150)
 office_start_time=models.TimeField(default=datetime_time(9,0))
 office_end_time=models.TimeField(default=datetime_time(18,0))
 grace_minutes=models.PositiveSmallIntegerField(default=10)
 updated_at=models.DateTimeField(auto_now=True)
 @classmethod
 def current(cls,company=None): return cls.objects.get_or_create(company=company)[0]
class Attendance(models.Model):
 class Status(models.TextChoices): PRESENT='Present','Present'; ABSENT='Absent','Absent'; HALF='Half-Day','Half day'; LATE='Late','Late'; LEAVE='On Leave','On leave'; WFH='WFH','WFH'
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='attendance'); date=models.DateField(default=timezone.localdate); check_in=models.DateTimeField(null=True,blank=True); check_out=models.DateTimeField(null=True,blank=True); check_in_latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True); check_in_longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True); check_out_latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True); check_out_longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True); total_hours=models.DecimalField(max_digits=5,decimal_places=2,default=0); status=models.CharField(max_length=20,choices=Status.choices,default=Status.PRESENT); late_minutes=models.PositiveSmallIntegerField(default=0); correction_note=models.TextField(blank=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['employee','date'],name='one_attendance_per_day')]; ordering=['-date']
class LeaveRequest(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='leave_requests'); leave_type=models.CharField(max_length=30,default='Casual'); start_date=models.DateField(); end_date=models.DateField(); total_days=models.PositiveSmallIntegerField(default=1); reason=models.TextField(); status=models.CharField(max_length=12,default='Pending'); comment=models.TextField(blank=True); applied_at=models.DateTimeField(auto_now_add=True); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
class WFHRequest(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='wfh_requests'); start_date=models.DateField(); end_date=models.DateField(); reason=models.TextField(); status=models.CharField(max_length=12,default='Pending'); comment=models.TextField(blank=True); applied_at=models.DateTimeField(auto_now_add=True); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
class SalaryStructure(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='salary_structures'); basic=models.DecimalField(max_digits=12,decimal_places=2); hra=models.DecimalField(max_digits=12,decimal_places=2,default=0); da=models.DecimalField(max_digits=12,decimal_places=2,default=0); bonus=models.DecimalField(max_digits=12,decimal_places=2,default=0); overtime_rate=models.DecimalField(max_digits=10,decimal_places=2,default=0); pf=models.DecimalField(max_digits=12,decimal_places=2,default=0); professional_tax=models.DecimalField(max_digits=12,decimal_places=2,default=0); income_tax=models.DecimalField(max_digits=12,decimal_places=2,default=0); other_deductions=models.DecimalField(max_digits=12,decimal_places=2,default=0); effective_from=models.DateField(default=timezone.localdate)
class Payroll(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='payrolls'); month=models.PositiveSmallIntegerField(); year=models.PositiveSmallIntegerField(); working_days=models.PositiveSmallIntegerField(default=22); present_days=models.PositiveSmallIntegerField(default=0); leave_days=models.PositiveSmallIntegerField(default=0); leave_deduction=models.DecimalField(max_digits=12,decimal_places=2,default=0); overtime_hours=models.DecimalField(max_digits=6,decimal_places=2,default=0); gross=models.DecimalField(max_digits=12,decimal_places=2); deductions=models.DecimalField(max_digits=12,decimal_places=2); net=models.DecimalField(max_digits=12,decimal_places=2); status=models.CharField(max_length=12,default='Generated'); adjustment_note=models.TextField(blank=True); generated_at=models.DateTimeField(auto_now_add=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['employee','month','year'],name='one_payroll_month_employee')]
class Holiday(models.Model):
 name=models.CharField(max_length=100); date=models.DateField(); kind=models.CharField(max_length=30,default='Fixed'); description=models.TextField(blank=True); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='holidays')
 class Meta: constraints=[models.UniqueConstraint(fields=['company','date'],name='unique_holiday_date_per_company')]
class Announcement(models.Model):
 title=models.CharField(max_length=200); message=models.TextField(); audience=models.CharField(max_length=12,default='ALL'); department=models.ForeignKey(Department,null=True,blank=True,on_delete=models.SET_NULL); author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='announcements'); created_at=models.DateTimeField(auto_now_add=True); expires_at=models.DateTimeField(null=True,blank=True)
class Notification(models.Model):
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='notifications'); title=models.CharField(max_length=200); message=models.TextField(); read_at=models.DateTimeField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
class ChatMessage(models.Model):
 sender=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='sent_chat_messages'); recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='received_chat_messages'); body=models.TextField(); created_at=models.DateTimeField(auto_now_add=True); read_at=models.DateTimeField(null=True,blank=True)
 class Meta: ordering=['created_at']
class Document(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='documents'); title=models.CharField(max_length=150); file=models.FileField(upload_to='employee-documents/%Y/%m/'); verified=models.BooleanField(default=False); uploaded_at=models.DateTimeField(auto_now_add=True)
class AuditLog(models.Model):
 user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.SET_NULL,related_name='audit_logs'); action=models.CharField(max_length=255); module=models.CharField(max_length=80); ip_address=models.GenericIPAddressField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
class AIChat(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.CASCADE); question=models.TextField(); answer=models.TextField(); created_at=models.DateTimeField(auto_now_add=True)
class PasswordOTP(models.Model):
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE); otp_hash=models.CharField(max_length=128); expires_at=models.DateTimeField(); used=models.BooleanField(default=False); created_at=models.DateTimeField(default=timezone.now)

class OvertimeRequest(models.Model):
 employee=models.ForeignKey(Employee,on_delete=models.PROTECT,related_name='overtime_requests'); date=models.DateField(); hours=models.DecimalField(max_digits=5,decimal_places=2); reason=models.TextField(blank=True); status=models.CharField(max_length=12,default='Pending'); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL); created_at=models.DateTimeField(auto_now_add=True)
class LeavePolicy(models.Model):
 leave_type=models.CharField(max_length=30); annual_days=models.PositiveSmallIntegerField(default=12); carry_forward=models.BooleanField(default=False); company=models.ForeignKey(Company,null=True,blank=True,on_delete=models.CASCADE,related_name='leave_policies')
 class Meta: constraints=[models.UniqueConstraint(fields=['company','leave_type'],name='unique_leave_policy_per_company')]
 def __str__(self): return self.leave_type


