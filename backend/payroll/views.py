import calendar, csv, os, io, zipfile, secrets, math
from datetime import timedelta
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.db.models import Q
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from .serializers import *
from .permissions import IsAdminOrSelf, IsAdminRole, IsAdminOrReadOnly, IsCompanyUser

def employee_for(user): return getattr(user,'employee',None)
def admin_only(user): return user.role=='ADMIN' or user.is_superuser
def company_for(user): return getattr(user,'company',None) or getattr(employee_for(user),'company',None)
def audit(request,action,module): AuditLog.objects.create(user=request.user,company=company_for(request.user),action=action,module=module,ip_address=request.META.get('REMOTE_ADDR'))

@api_view(['POST'])
@permission_classes([AllowAny])
def register_employee(request):
    return Response({'detail':'Employee accounts are created by their company administrator.'},status=status.HTTP_403_FORBIDDEN)

@api_view(['POST'])
@permission_classes([AllowAny])
def register_company(request):
    company_name=str(request.data.get('company_name','')).strip();first_name=str(request.data.get('first_name','')).strip();last_name=str(request.data.get('last_name','')).strip();email=str(request.data.get('email','')).strip().lower();password=request.data.get('password','')
    if not all([company_name,first_name,last_name,email,password]):return Response({'detail':'Company name, your name, work email, and password are required.'},status=400)
    if User.objects.filter(Q(email__iexact=email)|Q(username__iexact=email)).exists():return Response({'detail':'An account with this email already exists.'},status=400)
    if Company.objects.filter(name__iexact=company_name).exists():return Response({'detail':'A company with this name already has a Haven workspace.'},status=400)
    try:validate_password(password)
    except ValidationError as exc:return Response({'detail':list(exc.messages)},status=400)
    try:
        with transaction.atomic():
            company=Company.objects.create(name=company_name)
            user=User.objects.create_user(username=email,email=email,first_name=first_name,last_name=last_name,password=password,role='ADMIN',company=company)
    except IntegrityError:return Response({'detail':'Could not create this company account. Check that the company name and email are unique.'},status=400)
    refresh=RefreshToken.for_user(user)
    return Response({'access':str(refresh.access_token),'refresh':str(refresh),'company_id':company.pk},status=201)

@api_view(['POST'])
def change_password(request):
    old=request.data.get('old_password','');new=request.data.get('new_password','')
    if not request.user.check_password(old):return Response({'detail':'The current or temporary password is incorrect.'},status=400)
    try:validate_password(new,request.user)
    except ValidationError as exc:return Response({'detail':list(exc.messages)},status=400)
    request.user.set_password(new);request.user.must_change_password=False;request.user.save(update_fields=['password','must_change_password'])
    return Response({'detail':'Password changed successfully.'})

class EmployeeViewSet(viewsets.ModelViewSet):
 serializer_class=EmployeeSerializer; permission_classes=[IsAdminOrSelf]
 def get_queryset(self):
  q=Employee.objects.select_related('user','department','company')
  if not admin_only(self.request.user): return q.filter(user=self.request.user)
  company=company_for(self.request.user)
  if not company:return q.none()
  q=q.filter(company=company)
  search=self.request.query_params.get('search')
  if search:q=q.filter(Q(first_name__icontains=search)|Q(last_name__icontains=search)|Q(code__icontains=search)|Q(user__email__icontains=search)|Q(company_name__icontains=search)|Q(designation__icontains=search)|Q(department__name__icontains=search))
  for key in ('status','designation','department__name'):
   if self.request.query_params.get(key): q=q.filter(**{key:self.request.query_params[key]})
  if self.request.query_params.get('company_name'):q=q.filter(company_name__iexact=self.request.query_params['company_name'])
  return q
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  company=company_for(request.user)
  if not company:return Response({'detail':'This administrator is not assigned to a company.'},status=403)
  first=str(request.data.get('first_name','')).strip();last=str(request.data.get('last_name','')).strip();email=str(request.data.get('email','')).strip().lower()
  if not first or not last or not email:return Response({'detail':'First name, last name, and work email are required.'},status=400)
  if User.objects.filter(Q(email__iexact=email)|Q(username__iexact=email)).exists():return Response({'detail':'An account with this email already exists.'},status=400)
  department=None
  if request.data.get('department'):
   try:department=Department.objects.get(pk=request.data['department'],company=company)
   except (Department.DoesNotExist,ValueError,TypeError):return Response({'detail':'Choose a department from your company.'},status=400)
  temporary_password=secrets.token_urlsafe(10);code=f'EMP{company.pk:03d}-{secrets.token_hex(3).upper()}'
  try:
   with transaction.atomic():
    user=User.objects.create_user(username=email,email=email,first_name=first,last_name=last,password=temporary_password,role='EMPLOYEE',company=company,must_change_password=True)
    employee=Employee.objects.create(user=user,company=company,code=code,first_name=first,last_name=last,department=department,designation=str(request.data.get('designation','')).strip(),company_name=company.name)
  except IntegrityError:return Response({'detail':'Could not create the employee account. Check that the email address is unique.'},status=400)
  audit(request,'Created employee '+employee.code,'Employees')
  result=EmployeeSerializer(employee,context=self.get_serializer_context()).data;result['temporary_password']=temporary_password
  return Response(result,status=201)
 def perform_create(self,serializer):
  obj=serializer.save(); audit(self.request,'Created employee '+obj.code,'Employees')
 def perform_update(self,serializer):
  if not admin_only(self.request.user):
   obj=serializer.instance
   for key in ('phone','address','emergency_contact','profile_photo'):
    if key in self.request.data: setattr(obj,key,self.request.data[key])
   obj.save(update_fields=['company_name','phone','address','emergency_contact','profile_photo']);return
  company=company_for(self.request.user)
  department=serializer.validated_data.get('department',serializer.instance.department)
  if department and (not company or department.company_id!=company.pk):
   raise serializers.ValidationError({'department':'Choose a department from your company.'})
  obj=serializer.save();obj.user.first_name=obj.first_name;obj.user.last_name=obj.last_name;obj.user.is_active=obj.status=='Active';obj.user.save(update_fields=['first_name','last_name','is_active']);audit(self.request,'Updated employee '+obj.code+' status='+obj.status,'Employees')
  if obj.company_id!=company.pk or obj.company_name!=company.name:
   obj.company=company;obj.company_name=company.name;obj.save(update_fields=['company','company_name'])
 def destroy(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  emp=self.get_object(); emp.status=request.data.get('status','Terminated');
  if emp.status not in ['On Leave','Suspended','Resigned','Terminated']:emp.status='Terminated'
  emp.save(update_fields=['status']);emp.user.is_active=False;emp.user.save(update_fields=['is_active']);audit(request,'Deactivated employee '+emp.code,'Employees');return Response(status=204)
class AttendanceViewSet(viewsets.ModelViewSet):
 serializer_class=AttendanceSerializer; permission_classes=[IsAdminOrSelf]; http_method_names=['get','post','patch','head','options']
 def get_queryset(self):
  q=Attendance.objects.select_related('employee','employee__department')
  company=company_for(self.request.user)
  if not company:return q.none()
  if not admin_only(self.request.user): q=q.filter(employee=employee_for(self.request.user))
  else:q=q.filter(employee__company=company)
  params=self.request.query_params
  if params.get('from'):q=q.filter(date__gte=params['from'])
  if params.get('to'):q=q.filter(date__lte=params['to'])
  if params.get('month'):q=q.filter(date__month=params['month'])
  if params.get('year'):q=q.filter(date__year=params['year'])
  if params.get('status'):q=q.filter(status=params['status'])
  if params.get('department'):q=q.filter(employee__department_id=params['department'])
  if params.get('employee'):q=q.filter(employee_id=params['employee'])
  return q
 def create(self,request,*a,**kw):
  emp=employee_for(request.user)
  if not emp:return Response({'detail':'Employee profile required.'},status=403)
  settings=AttendanceSettings.current(company_for(request.user))
  if settings.office_latitude is None or settings.office_longitude is None:
   return Response({'detail':'The administrator must set the office location before attendance can be recorded.'},status=400)
  action_name=request.data.get('action')
  if action_name not in ('check_in','check_out'):
   return Response({'detail':'Choose check_in or check_out.'},status=400)
  latitude=longitude=None
  if action_name=='check_in':
   try:
    latitude=Decimal(str(request.data.get('latitude'))); longitude=Decimal(str(request.data.get('longitude')))
    if not (-90<=latitude<=90 and -180<=longitude<=180):raise InvalidOperation
   except (InvalidOperation,TypeError,ValueError):
    return Response({'detail':'A valid device location is required to check in. Turn on location access and try again.'},status=400)
   distance=distance_between_meters(float(settings.office_latitude),float(settings.office_longitude),float(latitude),float(longitude))
   if distance>settings.radius_meters:
    return Response({'detail':f'You are outside the office attendance area ({round(distance)} m away; limit {settings.radius_meters} m).'},status=403)
  today=timezone.localdate(); now=timezone.now(); row=Attendance.objects.filter(employee=emp,date=today).first()
  if action_name=='check_in':
   if row and row.check_in:return Response({'detail':'You have already checked in today.'},status=400)
   if row is None:row=Attendance(employee=emp,date=today)
   office_start=datetime.combine(today,settings.office_start_time).replace(tzinfo=timezone.get_current_timezone())
   row.check_in=now; row.check_in_latitude=latitude; row.check_in_longitude=longitude
   row.late_minutes=max(0,int((now-office_start).total_seconds()//60)-settings.grace_minutes)
   row.status='Late' if row.late_minutes else 'Present'; row.save()
  else:
   if not row or not row.check_in:return Response({'detail':'Check in before checking out.'},status=400)
   if row.check_out:return Response({'detail':'You have already checked out today.'},status=400)
   row.check_out=now; row.check_out_latitude=latitude; row.check_out_longitude=longitude
   row.total_hours=Decimal(str(round((now-row.check_in).total_seconds()/3600,2)))
   row.status='Half-Day' if row.total_hours<4 else ('Late' if row.late_minutes else 'Present'); row.save()
   expected_hours=(datetime.combine(today,settings.office_end_time)-datetime.combine(today,settings.office_start_time)).total_seconds()/3600
   if expected_hours<=0:expected_hours+=24
   extra=max(0,float(row.total_hours)-expected_hours)
   if extra>=0.25:OvertimeRequest.objects.create(employee=emp,date=today,hours=round(extra,2),reason='Automatically calculated from attendance')
  audit(request,'Attendance '+action_name.replace('_',' ')+' recorded','Attendance')
  return Response(AttendanceSerializer(row).data,status=201)
 def update(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  response=super().update(request,*a,**kw); row=self.get_object(); audit(request,'Corrected attendance: '+row.correction_note,'Attendance'); return response
 def partial_update(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return self.update(request,*a,**kw)

def distance_between_meters(lat1,lon1,lat2,lon2):
 radius=6371000
 p1,p2=math.radians(lat1),math.radians(lat2)
 dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
 a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return radius*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

@api_view(['GET','PATCH'])
@permission_classes([IsCompanyUser])
def attendance_settings(request):
 company=company_for(request.user)
 if not company:return Response({'detail':'This account is not assigned to a company.'},status=403)
 settings=AttendanceSettings.current(company)
 if request.method=='PATCH':
  if not admin_only(request.user):return Response({'detail':'Administrator access required.'},status=403)
  try:
   latitude=Decimal(str(request.data.get('office_latitude'))); longitude=Decimal(str(request.data.get('office_longitude')))
   radius=int(request.data.get('radius_meters')); start=datetime.strptime(request.data.get('office_start_time',''),'%H:%M').time(); end=datetime.strptime(request.data.get('office_end_time',''),'%H:%M').time(); grace=int(request.data.get('grace_minutes',10))
   if not (-90<=latitude<=90 and -180<=longitude<=180):raise ValueError
   if not (25<=radius<=5000):return Response({'detail':'Radius must be between 25 and 5,000 metres.'},status=400)
   if start==end:return Response({'detail':'Office start and end times must be different.'},status=400)
   if not (0<=grace<=120):return Response({'detail':'Grace time must be between 0 and 120 minutes.'},status=400)
  except (TypeError,ValueError,InvalidOperation):
   return Response({'detail':'Enter a valid office location, radius, and office hours.'},status=400)
  settings.office_latitude=latitude; settings.office_longitude=longitude; settings.radius_meters=radius; settings.office_start_time=start; settings.office_end_time=end; settings.grace_minutes=grace; settings.save()
  audit(request,'Updated office attendance location and hours','Attendance')
 return Response({'office_latitude':settings.office_latitude,'office_longitude':settings.office_longitude,'radius_meters':settings.radius_meters,'office_start_time':settings.office_start_time.strftime('%H:%M'),'office_end_time':settings.office_end_time.strftime('%H:%M'),'grace_minutes':settings.grace_minutes,'configured':settings.office_latitude is not None and settings.office_longitude is not None})
class LeaveViewSet(viewsets.ModelViewSet):
 serializer_class=LeaveSerializer; permission_classes=[IsAdminOrSelf]
 def get_queryset(self):
  q=LeaveRequest.objects.select_related('employee');params=self.request.query_params
  company=company_for(self.request.user)
  if not company:return q.none()
  if not admin_only(self.request.user):q=q.filter(employee=employee_for(self.request.user))
  else:q=q.filter(employee__company=company)
  if params.get('status'):q=q.filter(status=params['status'])
  if params.get('department'):q=q.filter(employee__department_id=params['department'])
  if params.get('from'):q=q.filter(start_date__gte=params['from'])
  if params.get('to'):q=q.filter(end_date__lte=params['to'])
  return q.order_by('-applied_at')
 def create(self,request,*a,**kw):
  emp=employee_for(request.user)
  if not emp:return Response({'detail':'Employee profile required.'},status=403)
  try: start=datetime.strptime(request.data['start_date'],'%Y-%m-%d').date(); end=datetime.strptime(request.data['end_date'],'%Y-%m-%d').date()
  except Exception:return Response({'detail':'Enter valid start and end dates.'},status=400)
  reason=str(request.data.get('reason','')).strip()
  if not reason:return Response({'detail':'Please provide a reason for your leave request.'},status=400)
  if end<start:return Response({'detail':'End date must be after start date.'},status=400)
  if LeaveRequest.objects.filter(employee=emp,status__in=['Pending','Approved'],start_date__lte=end,end_date__gte=start).exists():return Response({'detail':'These dates overlap an existing leave request.'},status=400)
  days=sum(1 for d in (start+timedelta(days=i) for i in range((end-start).days+1)) if d.weekday()<5 and not Holiday.objects.filter(company=company_for(request.user),date=d).exists())
  if days<1:return Response({'detail':'The selected range contains no working days.'},status=400)
  policy=LeavePolicy.objects.filter(company=company_for(request.user),leave_type__iexact=request.data.get('leave_type','Casual')).first()
  allowance=policy.annual_days if policy else 12
  used=emp.leave_requests.filter(status='Approved',leave_type=request.data.get('leave_type','Casual'),start_date__year=start.year).aggregate(v=Sum('total_days'))['v'] or 0
  pending=emp.leave_requests.filter(status='Pending',leave_type=request.data.get('leave_type','Casual'),start_date__year=start.year).aggregate(v=Sum('total_days'))['v'] or 0
  if used+pending+days>allowance and request.data.get('leave_type','Casual')!='Unpaid':return Response({'detail':f'Not enough {request.data.get("leave_type","Casual")} balance. Remaining: {max(0,allowance-used-pending)} day(s).'},status=400)
  row=LeaveRequest.objects.create(employee=emp,leave_type=request.data.get('leave_type','Casual'),start_date=start,end_date=end,total_days=days,reason=reason)
  admins=User.objects.filter(company=company_for(request.user),is_active=True,role='ADMIN')
  Notification.objects.bulk_create([Notification(user=admin,title='Leave request received',message=f'{emp} requested {days} day(s) of {row.leave_type} leave from {start} to {end}.') for admin in admins])
  return Response(LeaveSerializer(row).data,status=201)
 @action(detail=True,methods=['post'],url_path='review')
 def review(self,request,pk=None):
  if not admin_only(request.user):return Response(status=403)
  row=self.get_object(); decision=request.data.get('status')
  if decision not in ('Approved','Rejected'):return Response({'detail':'Choose Approved or Rejected.'},status=400)
  row.status=decision; row.comment=request.data.get('comment',''); row.reviewed_by=request.user; row.save();
  if decision=='Approved':
   d=row.start_date
   while d<=row.end_date:
    if d.weekday()<5 and not Holiday.objects.filter(company=row.employee.company,date=d).exists():Attendance.objects.update_or_create(employee=row.employee,date=d,defaults={'status':'On Leave'})
    d+=timedelta(days=1)
  Notification.objects.create(user=row.employee.user,title='Leave request '+decision,message=row.comment or f'Your leave request was {decision.lower()}.'); audit(request,f'{decision} leave #{row.pk}','Leave'); return Response(LeaveSerializer(row).data)
class WFHViewSet(viewsets.ModelViewSet):
 serializer_class=WFHSerializer; permission_classes=[IsAdminOrSelf]
 def get_queryset(self):
  q=WFHRequest.objects.select_related('employee');params=self.request.query_params
  company=company_for(self.request.user)
  if not company:return q.none()
  if not admin_only(self.request.user):q=q.filter(employee=employee_for(self.request.user))
  else:q=q.filter(employee__company=company)
  if params.get('status'):q=q.filter(status=params['status'])
  if params.get('from'):q=q.filter(start_date__gte=params['from'])
  if params.get('to'):q=q.filter(end_date__lte=params['to'])
  if params.get('department'):q=q.filter(employee__department_id=params['department'])
  return q
 def create(self,request,*a,**kw):
  emp=employee_for(request.user)
  if not emp:return Response({'detail':'Employee profile required.'},status=403)
  try: start=datetime.strptime(request.data['start_date'],'%Y-%m-%d').date(); end=datetime.strptime(request.data['end_date'],'%Y-%m-%d').date()
  except Exception:return Response({'detail':'Enter valid start and end dates.'},status=400)
  reason=str(request.data.get('reason','')).strip()
  if not reason:return Response({'detail':'Please provide a reason for your WFH request.'},status=400)
  if end<start:return Response({'detail':'End date must not be before start date.'},status=400)
  if WFHRequest.objects.filter(employee=emp,status__in=['Pending','Approved'],start_date__lte=end,end_date__gte=start).exists():return Response({'detail':'These dates overlap an existing WFH request.'},status=400)
  row=WFHRequest.objects.create(employee=emp,start_date=start,end_date=end,reason=reason)
  admins=User.objects.filter(company=company_for(request.user),is_active=True,role='ADMIN')
  Notification.objects.bulk_create([Notification(user=admin,title='WFH request received',message=f'{emp} requested to work from home from {start} to {end}.') for admin in admins])
  return Response(WFHSerializer(row).data,status=201)
 @action(detail=True,methods=['post'],url_path='review')
 def review(self,request,pk=None):
  if not admin_only(request.user):return Response(status=403)
  row=self.get_object(); decision=request.data.get('status')
  if decision not in ('Approved','Rejected'):return Response({'detail':'Choose Approved or Rejected.'},status=400)
  row.status=decision; row.comment=request.data.get('comment',''); row.reviewed_by=request.user; row.save()
  if row.status=='Approved':
   from datetime import timedelta
   d=row.start_date
   while d<=row.end_date:
    Attendance.objects.update_or_create(employee=row.employee,date=d,defaults={'status':'WFH'}); d+=timedelta(days=1)
  Notification.objects.create(user=row.employee.user,title='WFH request '+row.status,message=row.comment or f'Your WFH request from {row.start_date} to {row.end_date} was {row.status.lower()}.'); audit(request,f'{decision} WFH #{row.pk}','WFH'); return Response(WFHSerializer(row).data)
class PayrollViewSet(viewsets.ModelViewSet):
 serializer_class=PayrollSerializer; permission_classes=[IsAdminOrSelf]
 def get_queryset(self):
  q=Payroll.objects.select_related('employee');params=self.request.query_params;company=company_for(self.request.user)
  if not company:return q.none()
  if not admin_only(self.request.user):q=q.filter(employee=employee_for(self.request.user),status='Finalized')
  else:q=q.filter(employee__company=company)
  if params.get('month'):q=q.filter(month=params['month'])
  if params.get('year'):q=q.filter(year=params['year'])
  if params.get('status') and admin_only(self.request.user):q=q.filter(status=params['status'])
  if params.get('employee') and admin_only(self.request.user):q=q.filter(employee_id=params['employee'])
  if params.get('department') and admin_only(self.request.user):q=q.filter(employee__department_id=params['department'])
  return q
 def create(self,request,*a,**kw): return Response(status=405)
 def update(self,request,*a,**kw):
  if not admin_only(request.user): return Response(status=403)
  row=self.get_object()
  if row.status=='Finalized' and not request.data.get('override'): return Response({'detail':'Finalized payroll is locked. Supply override=true to reopen it.'},status=409)
  if row.status=='Finalized': audit(request,'Reopened finalized payroll '+str(row.pk),'Payroll')
  data=request.data.copy(); data.pop('override',None); ser=self.get_serializer(row,data=data,partial=kw.get('partial',False)); ser.is_valid(raise_exception=True); ser.save(status='Generated'); audit(request,'Adjusted payroll '+str(row.pk)+': '+data.get('adjustment_note',''), 'Payroll'); return Response(ser.data)
 @action(detail=False,methods=['post'])
 def generate(self,request):
  if not admin_only(request.user):return Response(status=403)
  try: month=int(request.data.get('month',timezone.localdate().month)); year=int(request.data.get('year',timezone.localdate().year))
  except (TypeError,ValueError): return Response({'detail':'Enter a valid payroll month and year.'},status=400)
  if month<1 or month>12 or year<2000 or year>timezone.localdate().year:return Response({'detail':'Enter a valid payroll month and year.'},status=400)
  today=timezone.localdate()
  if (year,month)>(today.year,today.month):return Response({'detail':'Payroll cannot be generated for a future month.'},status=400)
  created=[]; skipped=[]
  company=company_for(request.user)
  if not company:return Response({'detail':'This administrator is not assigned to a company.'},status=403)
  employees=Employee.objects.filter(company=company,status='Active')
  if request.data.get('employee_ids'): employees=employees.filter(id__in=request.data['employee_ids'])
  for emp in employees:
   start=datetime(year,month,1).date(); end=datetime(year,month,calendar.monthrange(year,month)[1]).date(); period_end=min(end,today)
   structure=emp.salary_structures.filter(effective_from__lte=start).order_by('-effective_from').first()
   if not structure: skipped.append(emp.code+' (missing salary setup)'); continue
   holidays=set(Holiday.objects.filter(company=company,date__range=(start,end)).values_list('date',flat=True))
   work_dates={datetime(year,month,day).date() for day in range(1,end.day+1) if datetime(year,month,day).weekday()<5 and datetime(year,month,day).date() not in holidays}
   working=max(len(work_dates),1)
   attendance=emp.attendance.filter(date__range=(start,period_end))
   present=attendance.filter(status__in=['Present','Late','WFH']).count()
   absent_dates=set(attendance.filter(status='Absent').values_list('date',flat=True))
   leave_rows=emp.leave_requests.filter(status='Approved',start_date__lte=period_end,end_date__gte=start)
   approved_leave_dates=set(); unpaid_leave_dates=set()
   for leave_row in leave_rows:
    first=max(leave_row.start_date,start); last=min(leave_row.end_date,period_end); cursor=first
    while cursor<=last:
     if cursor in work_dates:
      approved_leave_dates.add(cursor)
      if leave_row.leave_type.strip().lower() in ('unpaid','lop','loss of pay'): unpaid_leave_dates.add(cursor)
     cursor+=timedelta(days=1)
   leave_days=len(approved_leave_dates)
   leave_deduction=(structure.basic/working)*len(absent_dates|unpaid_leave_dates)
   approved_ot=emp.overtime_requests.filter(status='Approved',date__year=year,date__month=month).aggregate(v=Sum('hours'))['v'] or Decimal('0')
   overtime_pay=approved_ot*structure.overtime_rate
   gross=structure.basic+structure.hra+structure.da+structure.bonus+overtime_pay
   deduction=structure.pf+structure.professional_tax+structure.income_tax+structure.other_deductions+leave_deduction
   net=gross-deduction
   existing=Payroll.objects.filter(employee=emp,month=month,year=year).first()
   if existing and existing.status=='Finalized' and not request.data.get('override_finalized'):skipped.append(emp.code+' (already finalized)');continue
   if existing and existing.status=='Finalized':audit(request,f'Reopened finalized payroll for regeneration #{existing.pk}','Payroll')
   row,_=Payroll.objects.update_or_create(employee=emp,month=month,year=year,defaults={'working_days':working,'present_days':present,'leave_days':leave_days,'leave_deduction':leave_deduction,'gross':gross,'deductions':deduction,'net':net,'overtime_hours':approved_ot,'status':'Generated'}); created.append(row)
  audit(request,f'Generated payroll {month}/{year}','Payroll'); return Response({'generated':PayrollSerializer(created,many=True).data,'missing_salary_structure':skipped})
 @action(detail=True,methods=['post'])
 def finalize(self,request,pk=None):
  if not admin_only(request.user):return Response(status=403)
  row=self.get_object(); row.status='Finalized'; row.save(update_fields=['status']); audit(request,'Finalized payroll '+str(row.pk),'Payroll');Notification.objects.create(user=row.employee.user,title='Payslip ready',message=f'Your {calendar.month_name[row.month]} {row.year} payslip is available.');return Response(PayrollSerializer(row).data)
class AnnouncementViewSet(viewsets.ModelViewSet):
 serializer_class=AnnouncementSerializer; permission_classes=[IsAdminOrReadOnly]
 def get_queryset(self):
  company=company_for(self.request.user)
  if not company:return Announcement.objects.none()
  q=Announcement.objects.filter(company=company).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).order_by('-created_at'); return q if admin_only(self.request.user) else q.filter(audience__in=['ALL','EMPLOYEE']).filter(Q(department__isnull=True)|Q(department=employee_for(self.request.user).department if employee_for(self.request.user) else None))
 def perform_create(self,serializer):
  if not admin_only(self.request.user):raise serializers.ValidationError('Only a company administrator can publish an announcement.')
  if not company_for(self.request.user):raise serializers.ValidationError('Administrator must belong to a company.')
  obj=serializer.save(author=self.request.user)
  obj.company=company_for(self.request.user);obj.save(update_fields=['company'])
  recipients=User.objects.filter(company=obj.company,is_active=True,role='EMPLOYEE')
  if obj.audience=='ADMIN':recipients=User.objects.filter(company=obj.company,is_active=True,role='ADMIN')
  if obj.department_id:recipients=recipients.filter(employee__department_id=obj.department_id)
  Notification.objects.bulk_create([Notification(user=u,title=obj.title,message=obj.message) for u in recipients])
  audit(self.request,'Published announcement '+obj.title,'Announcements')
 def _validate_department(self,request):
  department_id=request.data.get('department')
  if department_id in (None,''):return
  if not Department.objects.filter(pk=department_id,company=company_for(request.user)).exists():
   raise serializers.ValidationError({'department':'Choose a department from your company.'})
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  self._validate_department(request)
  return super().create(request,*a,**kw)
 def update(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  self._validate_department(request)
  return super().update(request,*a,**kw)
 def destroy(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().destroy(request,*a,**kw)
class HolidayViewSet(viewsets.ModelViewSet):
 serializer_class=HolidaySerializer; permission_classes=[IsAdminOrReadOnly]
 def get_queryset(self):
  company=company_for(self.request.user)
  return Holiday.objects.filter(company=company).order_by('date') if company else Holiday.objects.none()
 def perform_create(self,serializer):
  company=company_for(self.request.user)
  if not company:raise serializers.ValidationError('Administrator must belong to a company.')
  holiday=serializer.save(company=company);when=max(0,(holiday.date-timezone.localdate()).days)
  if when<=30:
   Notification.objects.bulk_create([Notification(user=u,title='Upcoming holiday: '+holiday.name,message=f'{holiday.date} · {holiday.kind}') for u in User.objects.filter(company=company,role='EMPLOYEE',is_active=True)])
  audit(self.request,'Created holiday '+holiday.name,'Holidays')
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().create(request,*a,**kw)
 def update(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().update(request,*a,**kw)
 def destroy(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().destroy(request,*a,**kw)
class DepartmentViewSet(viewsets.ModelViewSet):
 serializer_class=DepartmentSerializer; permission_classes=[IsAdminOrReadOnly]
 def get_queryset(self):
  company=company_for(self.request.user)
  return Department.objects.filter(company=company) if company else Department.objects.none()
 def perform_create(self,serializer):
  if not company_for(self.request.user):raise serializers.ValidationError('This account is not assigned to a company.')
  serializer.save(company=company_for(self.request.user))
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().create(request,*a,**kw)
class ShiftViewSet(viewsets.ModelViewSet):
 serializer_class=ShiftSerializer; permission_classes=[IsAdminOrReadOnly]
 def get_queryset(self):
  company=company_for(self.request.user)
  return Shift.objects.filter(company=company) if company else Shift.objects.none()
 def perform_create(self,serializer):
  if not company_for(self.request.user):raise serializers.ValidationError('This account is not assigned to a company.')
  serializer.save(company=company_for(self.request.user))
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return super().create(request,*a,**kw)
class SalaryViewSet(viewsets.ModelViewSet):
 serializer_class=SalarySerializer; permission_classes=[IsAdminOrSelf]
 def get_queryset(self):
  q=SalaryStructure.objects.select_related('employee').order_by('-effective_from','-id')
  company=company_for(self.request.user)
  if not company:return q.none()
  q=q.filter(employee__company=company)
  if not admin_only(self.request.user):return q.filter(employee=employee_for(self.request.user))
  if self.request.query_params.get('employee'):q=q.filter(employee_id=self.request.query_params['employee'])
  return q
 def create(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  if not Employee.objects.filter(pk=request.data.get('employee'),company=company_for(request.user)).exists():return Response({'detail':'Choose an employee from your company.'},status=400)
  return super().create(request,*a,**kw)
 def perform_create(self,serializer):
  row=serializer.save();audit(self.request,f'Set salary structure for {row.employee.code} effective {row.effective_from}','Payroll')
 def update(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  previous=self.get_object(); data={key:getattr(previous,key) for key in ['basic','hra','da','bonus','overtime_rate','pf','professional_tax','income_tax','other_deductions','effective_from']};data.update(request.data);data['employee']=previous.employee_id
  ser=self.get_serializer(data=data);ser.is_valid(raise_exception=True);obj=ser.save();audit(request,f'Created salary structure version for {obj.employee.code}','Salary');return Response(self.get_serializer(obj).data,status=201)
 partial_update=update
 def destroy(self,request,*a,**kw):
  if not admin_only(request.user):return Response(status=403)
  return Response({'detail':'Salary history is retained. Create a new effective version instead.'},status=405)
class DocumentViewSet(viewsets.ModelViewSet):
 serializer_class=DocumentSerializer; permission_classes=[IsAdminOrSelf]
 http_method_names=['get','post','patch','delete','head','options']
 def get_queryset(self):
  q=Document.objects.select_related('employee');company=company_for(self.request.user)
  if not company:return q.none()
  return q.filter(employee__company=company) if admin_only(self.request.user) else q.filter(employee=employee_for(self.request.user))
 def update(self,request,*args,**kwargs):
  if set(request.data.keys())-{'title'}: return Response({'detail':'Only the document name can be edited here.'},status=400)
  kwargs['partial']=True
  return super().update(request,*args,**kwargs)
 partial_update=update
 def perform_destroy(self,instance):
  stored_file=instance.file
  instance.delete()
  if stored_file: stored_file.delete(save=False)
 def perform_create(self,serializer):
  emp=Employee.objects.filter(pk=self.request.data.get('employee'),company=company_for(self.request.user)).first() if admin_only(self.request.user) else employee_for(self.request.user)
  if not emp: raise serializers.ValidationError('Employee profile required.')
  f=self.request.FILES.get('file')
  if not f or f.size>10*1024*1024 or f.content_type not in ['application/pdf','image/png','image/jpeg']: raise serializers.ValidationError('Upload a PDF, PNG, or JPG under 10 MB.')
  serializer.save(employee=emp)
 @action(detail=True,methods=['post'],url_path='verify')
 def verify(self,request,pk=None):
  if not admin_only(request.user):return Response(status=403)
  doc=self.get_object();doc.verified=bool(request.data.get('verified',True));doc.save(update_fields=['verified']);audit(request,('Verified' if doc.verified else 'Unverified')+' document '+str(doc.pk),'Documents');return Response(DocumentSerializer(doc).data)
 @action(detail=True,methods=['get'],url_path='download')
 def download(self,request,pk=None):
  doc=self.get_object()
  from django.http import FileResponse
  return FileResponse(doc.file.open('rb'),as_attachment=True,filename=doc.file.name.split('/')[-1])
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
 serializer_class=NotificationSerializer
 def get_queryset(self): return self.request.user.notifications.order_by('-created_at')
 @action(detail=True,methods=['post'])
 def read(self,request,pk=None):
  n=self.get_object(); n.read_at=timezone.now(); n.save(update_fields=['read_at']); return Response({'ok':True})
class ChatMessageViewSet(viewsets.ModelViewSet):
 serializer_class=ChatMessageSerializer
 permission_classes=[IsAdminOrSelf]
 http_method_names=['get','post','head','options']
 def get_queryset(self):
  company=company_for(self.request.user)
  if not company:return ChatMessage.objects.none()
  return ChatMessage.objects.filter(Q(sender=self.request.user)|Q(recipient=self.request.user),sender__company=company,recipient__company=company).select_related('sender','recipient')
 def create(self,request,*args,**kwargs):
  if not company_for(request.user):return Response({'detail':'This account is not assigned to a company.'},status=403)
  recipient_id=request.data.get('recipient'); body=str(request.data.get('body','')).strip()
  if not body: return Response({'detail':'Write a message before sending.'},status=400)
  if len(body)>5000: return Response({'detail':'Messages must be 5,000 characters or fewer.'},status=400)
  try: recipient=User.objects.get(pk=recipient_id,is_active=True,company=company_for(request.user))
  except (User.DoesNotExist,TypeError,ValueError): return Response({'detail':'Choose a valid recipient.'},status=400)
  sender=request.user
  if sender.pk==recipient.pk or admin_only(sender)==admin_only(recipient): return Response({'detail':'Messages can only be sent between an employee and an administrator.'},status=403)
  message=ChatMessage.objects.create(sender=sender,recipient=recipient,body=body)
  return Response(self.get_serializer(message).data,status=201)
 @action(detail=False,methods=['get'])
 def contacts(self,request):
  company=company_for(request.user)
  if not company:return Response([])
  if admin_only(request.user):
   contacts=User.objects.filter(company=company,role='EMPLOYEE',is_active=True,employee__isnull=False).select_related('employee').order_by('first_name','last_name')
  else:
   contacts=User.objects.filter(company=company,role='ADMIN',is_active=True).order_by('first_name','last_name')
  return Response([{'id':u.pk,'name':u.get_full_name() or u.username,'email':u.email,'role':'ADMIN' if admin_only(u) else 'EMPLOYEE'} for u in contacts])
 @action(detail=True,methods=['post'],url_path='read')
 def mark_read(self,request,pk=None):
  message=self.get_object()
  if message.recipient_id!=request.user.pk: return Response(status=403)
  if not message.read_at: message.read_at=timezone.now();message.save(update_fields=['read_at'])
  return Response({'ok':True})
@api_view(['GET'])
def me(request):
 company=company_for(request.user)
 return Response({'id':request.user.id,'name':request.user.get_full_name() or request.user.username,'email':request.user.email,'role':'ADMIN' if admin_only(request.user) else request.user.role,'employee_id':getattr(employee_for(request.user),'id',None),'company_id':company.pk if company else None,'company_name':company.name if company else '', 'must_change_password':request.user.must_change_password})
def headcount_trend(company):
    today=timezone.localdate();out=[]
    for offset in range(11,-1,-1):
        year=today.year;month=today.month-offset
        while month<=0:year-=1;month+=12
        end=calendar.monthrange(year,month)[1];cutoff=datetime(year,month,end).date()
        out.append({'name':calendar.month_abbr[month],'people':Employee.objects.filter(company=company,joining_date__lte=cutoff,status='Active').count()})
    return out
def payroll_trend(company):
    today=timezone.localdate();out=[]
    for offset in range(11,-1,-1):
        year=today.year;month=today.month-offset
        while month<=0:year-=1;month+=12
        amount=Payroll.objects.filter(employee__company=company,year=year,month=month).aggregate(v=Sum('net'))['v'] or 0
        out.append({'name':calendar.month_abbr[month],'pay':float(amount)/100000})
    return out
def leave_balances(employee,year):
    policies=list(LeavePolicy.objects.filter(company=employee.company));types={p.leave_type:p.annual_days for p in policies};types.setdefault('Casual',12);types.setdefault('Sick',8)
    result={}
    for leave_type,days in types.items():
        used=employee.leave_requests.filter(status='Approved',leave_type__iexact=leave_type,start_date__year=year).aggregate(v=Sum('total_days'))['v'] or 0
        result[leave_type]=max(0,days-used)
    return result
@api_view(['GET'])
def dashboard(request):
 emp=employee_for(request.user); today=timezone.localdate(); company=company_for(request.user)
 if not company:return Response({'detail':'This account is not assigned to a company.'},status=403)
 if admin_only(request.user):
  employees=Employee.objects.filter(company=company,status='Active');attendance=Attendance.objects.filter(employee__company=company);leaves=LeaveRequest.objects.filter(employee__company=company);wfh=WFHRequest.objects.filter(employee__company=company);payroll=Payroll.objects.filter(employee__company=company)
  return Response({'role':'ADMIN','employee_count':employees.count(),'present_today':attendance.filter(date=today,status__in=['Present','Late','WFH']).count(),'pending_leaves':leaves.filter(status='Pending').count(),'pending_wfh':wfh.filter(status='Pending').count(),'payroll_total':payroll.filter(month=today.month,year=today.year).aggregate(s=Sum('net'))['s'] or 0,'recent_attendance':AttendanceSerializer(attendance.select_related('employee').order_by('-date')[:6],many=True).data,'pending_requests':list(leaves.filter(status='Pending').select_related('employee').values('id','employee__first_name','employee__last_name','leave_type','start_date','end_date')[:5]),'attendance_rate':round(attendance.filter(date=today,status__in=['Present','Late','WFH']).count()/max(employees.count(),1)*100,1),'headcount_trend':headcount_trend(company),'payroll_trend':payroll_trend(company)})
 announcements=Announcement.objects.filter(company=company,audience__in=['ALL','EMPLOYEE']).order_by('-created_at')[:3]
 return Response({'role':'EMPLOYEE','name':str(emp) if emp else request.user.get_full_name(),'today':AttendanceSerializer(emp.attendance.filter(date=today).first()).data if emp and emp.attendance.filter(date=today).exists() else None,'attendance_count':emp.attendance.filter(date__month=today.month,date__year=today.year).count() if emp else 0,'leave_balance':leave_balances(emp,today.year) if emp else {'Casual':12,'Sick':8},'latest_payroll':PayrollSerializer(emp.payrolls.filter(status='Finalized').order_by('-year','-month').first()).data if emp and emp.payrolls.filter(status='Finalized').exists() else None,'announcements':AnnouncementSerializer(announcements,many=True).data})
@api_view(['POST'])
def assistant(request):
 emp=employee_for(request.user); question=request.data.get('question','').strip()
 if not question:return Response({'detail':'Ask a question first.'},status=400)
 data=''
 if emp:
  pay=emp.payrolls.filter(status='Finalized').order_by('-year','-month').first()
  if pay:data=f"Your latest finalized payslip is {calendar.month_name[pay.month]} {pay.year}: gross ?{pay.gross}, deductions ?{pay.deductions}, net ?{pay.net}."
  if 'salary' in question.lower() and pay:
   answer=data
  elif 'leave' in question.lower():
   leave_type='Sick' if 'sick' in question.lower() else 'Casual';policy=LeavePolicy.objects.filter(company=emp.company,leave_type__iexact=leave_type).first();allowance=policy.annual_days if policy else (8 if leave_type=='Sick' else 12);used=emp.leave_requests.filter(status='Approved',leave_type__iexact=leave_type,start_date__year=timezone.localdate().year).aggregate(v=Sum('total_days'))['v'] or 0;answer=f'Your {leave_type.lower()} leave balance is {max(0,allowance-used)} of {allowance} days. Weekends and holidays are excluded. Requests need administrator approval.'
  elif 'attendance' in question.lower():
   month=timezone.localdate().month;rows=emp.attendance.filter(date__month=month,date__year=timezone.localdate().year);late=rows.filter(status='Late').count();answer=f'This month you have {late} late arrival(s), {rows.filter(status="Absent").count()} absence(s), and {rows.aggregate(v=Sum("total_hours"))["v"] or 0} recorded work hours.'
  else:
   key=os.getenv('GEMINI_API_KEY')
   if key:
    try:
     import urllib.request, json
     payload=json.dumps({'contents':[{'parts':[{'text':f'You are a concise HR assistant. Answer using only this employee context: {data or "No finalized payslip is available."}. If asked for another employee data, refuse. Question: {question}'}]}]}).encode()
     req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key='+key,data=payload,headers={'Content-Type':'application/json'})
     answer=json.loads(urllib.request.urlopen(req,timeout=8).read())['candidates'][0]['content']['parts'][0]['text']
    except Exception: answer='The AI helper is temporarily unavailable. Attendance, leave, and payroll features are still available.'
   else: answer='I can help with leave, attendance, and payslip questions. Add a Gemini API key to enable open-ended answers.'
  AIChat.objects.create(employee=emp,question=question,answer=answer)
 else: answer='Employee profile is not linked to this account.'
 return Response({'answer':answer})

@api_view(['GET'])
def attendance_insights(request):
    emp=employee_for(request.user)
    if not emp:return Response(status=403)
    month=int(request.query_params.get('month',timezone.localdate().month));year=int(request.query_params.get('year',timezone.localdate().year));rows=emp.attendance.filter(date__year=year,date__month=month)
    late=rows.filter(status='Late').count();absent=rows.filter(status='Absent').count();hours=rows.aggregate(v=Sum('total_hours'))['v'] or 0
    text=f'In {calendar.month_name[month]}, you checked in late {late} time(s), had {absent} absence(s), and worked {hours} hours across {rows.count()} attendance record(s).'
    key=os.getenv('GEMINI_API_KEY')
    if key:
        try:
            import urllib.request,json
            body=json.dumps({'contents':[{'parts':[{'text':f'Summarize this employee attendance trend, offer one supportive suggestion, no sensitive inference: {text}'}]}]}).encode();req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key='+key,data=body,headers={'Content-Type':'application/json'});text=json.loads(urllib.request.urlopen(req,timeout=8).read())['candidates'][0]['content']['parts'][0]['text']
        except Exception:pass
    return Response({'insight':text,'late_count':late,'absent_count':absent,'total_hours':hours})

@api_view(['GET'])
def old_export_report(request):
 if not admin_only(request.user):return Response(status=403)
 company=company_for(request.user)
 if not company:return Response(status=403)
 response=HttpResponse(content_type='text/csv'); response['Content-Disposition']='attachment; filename="epms-payroll-report.csv"'; writer=csv.writer(response); writer.writerow(['Employee code','Employee','Month','Year','Gross','Deductions','Net','Status'])
 for p in Payroll.objects.select_related('employee').filter(employee__company=company).order_by('-year','-month'):writer.writerow([p.employee.code,str(p.employee),p.month,p.year,p.gross,p.deductions,p.net,p.status])
 return response
@api_view(['GET'])
def payslip(request,pk):
 try: p=Payroll.objects.select_related('employee').get(pk=pk)
 except Payroll.DoesNotExist:return Response(status=404)
 if admin_only(request.user):
  if not company_for(request.user) or p.employee.company_id!=company_for(request.user).id:return Response(status=403)
 elif not employee_for(request.user) or p.employee_id!=employee_for(request.user).id:return Response(status=403)
 if p.status!='Finalized':return Response({'detail':'Payslip is available after payroll is finalized.'},status=400)
 from reportlab.lib.pagesizes import letter
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
 from reportlab.lib.enums import TA_CENTER
 buff=io.BytesIO();doc=SimpleDocTemplate(buff,pagesize=letter,rightMargin=50,leftMargin=50,topMargin=46,bottomMargin=46);styles=getSampleStyleSheet();brand=ParagraphStyle('Brand',parent=styles['Title'],textColor=colors.HexColor('#6256b7'),alignment=TA_CENTER,fontSize=21);sub=ParagraphStyle('Sub',parent=styles['Normal'],textColor=colors.HexColor('#777777'),alignment=TA_CENTER);story=[Paragraph('HAVEN ? PEOPLE & PAYROLL',brand),Paragraph('MONTHLY PAYSLIP',sub),Spacer(1,22),Paragraph(f'<b>Employee:</b> {p.employee} &nbsp;&nbsp; <b>Code:</b> {p.employee.code}',styles['Normal']),Paragraph(f'<b>Pay period:</b> {calendar.month_name[p.month]} {p.year} &nbsp;&nbsp; <b>Reference:</b> EPMS-{p.year}{p.month:02d}-{p.employee.code}-{p.pk:06d}',styles['Normal']),Spacer(1,18)];structure=p.employee.salary_structures.filter(effective_from__lte=datetime(p.year,p.month,1).date()).order_by('-effective_from').first();earnings=[['Earnings','Amount (INR)']];deductions=[['Deductions','Amount (INR)']];
 if structure:earnings += [['Basic',str(structure.basic)],['HRA',str(structure.hra)],['DA',str(structure.da)],['Bonus',str(structure.bonus)],['Approved overtime',str(p.overtime_hours*structure.overtime_rate)]];deductions += [['PF',str(structure.pf)],['Professional tax',str(structure.professional_tax)],['Income tax',str(structure.income_tax)],['Other deductions',str(structure.other_deductions)]]
 earnings += [['Gross pay',str(p.gross)]];deductions += [['Unpaid leave / absence',str(p.leave_deduction)],['Total deductions',str(p.deductions)]]
 for data in (earnings,deductions):
  table=Table(data,colWidths=[360,130],hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f0eefb')),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#51459e')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#e4e4ed')),('ALIGN',(1,0),(1,-1),'RIGHT'),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)]));story.extend([table,Spacer(1,14)])
 story.append(Paragraph(f'<b>NET PAY: INR {p.net}</b>',ParagraphStyle('Net',parent=styles['Heading2'],textColor=colors.HexColor('#3e8d70'))));doc.build(story);response=HttpResponse(buff.getvalue(),content_type='application/pdf');response['Content-Disposition']=f'attachment; filename="payslip-{p.year}-{p.month:02d}.pdf"';return response


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    from rest_framework_simplejwt.tokens import RefreshToken
    token=request.data.get('refresh')
    if token:
        try: RefreshToken(token).blacklist()
        except Exception: pass
    return Response({'detail':'Signed out.'},status=200)

class OvertimeViewSet(viewsets.ModelViewSet):
    serializer_class=OvertimeSerializer; permission_classes=[IsAdminOrSelf]
    def get_queryset(self):
        q=OvertimeRequest.objects.select_related('employee');company=company_for(self.request.user)
        if not company:return q.none()
        return q.filter(employee__company=company) if admin_only(self.request.user) else q.filter(employee=employee_for(self.request.user))
    def create(self,request,*args,**kwargs):
        emp=employee_for(request.user)
        if not emp:return Response(status=403)
        try: row=OvertimeRequest.objects.create(employee=emp,date=request.data['date'],hours=request.data['hours'],reason=request.data.get('reason',''))
        except Exception as e:return Response({'detail':str(e)},status=400)
        return Response(OvertimeSerializer(row).data,status=201)
    @action(detail=True,methods=['post'],url_path='review')
    def review(self,request,pk=None):
        if not admin_only(request.user):return Response(status=403)
        row=self.get_object(); decision=request.data.get('status')
        if decision not in ['Approved','Rejected']:return Response({'detail':'Choose Approved or Rejected.'},status=400)
        row.status=decision; row.reviewed_by=request.user; row.save(); audit(request,f'{decision} overtime #{row.pk}','Overtime'); Notification.objects.create(user=row.employee.user,title='Overtime '+decision,message=f'Your overtime for {row.date} was {decision.lower()}.'); return Response(OvertimeSerializer(row).data)
class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class=SimpleSerializer; permission_classes=[IsAdminRole]
    def get_queryset(self):
        company=company_for(self.request.user)
        return ShiftAssignment.objects.select_related('employee','shift').filter(employee__company=company,shift__company=company) if company else ShiftAssignment.objects.none()
    def get_serializer_class(self):
        class AssignmentSerializer(serializers.ModelSerializer):
            employee_name=serializers.CharField(source='employee.__str__',read_only=True)
            shift_name=serializers.CharField(source='shift.name',read_only=True)
            class Meta: model=ShiftAssignment; fields='__all__'
        return AssignmentSerializer
    def perform_create(self,serializer):
        company=company_for(self.request.user);employee=serializer.validated_data['employee'];shift=serializer.validated_data['shift']
        if not company or employee.company_id!=company.pk or shift.company_id!=company.pk:raise serializers.ValidationError('Employee and shift must belong to your company.')
        serializer.save(); audit(self.request,'Assigned shift','Shifts')
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=AuditSerializer; permission_classes=[IsAdminRole]
    def get_queryset(self):
        company=company_for(self.request.user)
        if not company:return AuditLog.objects.none()
        q=AuditLog.objects.select_related('user').filter(company=company).order_by('-created_at')
        if self.request.query_params.get('module'):q=q.filter(module__icontains=self.request.query_params['module'])
        if self.request.query_params.get('user'):q=q.filter(user__username__icontains=self.request.query_params['user'])
        if self.request.query_params.get('from'):q=q.filter(created_at__date__gte=self.request.query_params['from'])
        if self.request.query_params.get('to'):q=q.filter(created_at__date__lte=self.request.query_params['to'])
        return q
class LeavePolicyViewSet(viewsets.ModelViewSet):
    serializer_class=LeavePolicySerializer; permission_classes=[IsAdminOrReadOnly]
    def get_queryset(self):
        company=company_for(self.request.user)
        return LeavePolicy.objects.filter(company=company) if company else LeavePolicy.objects.none()
    def perform_create(self,serializer):serializer.save(company=company_for(self.request.user))
class AIHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=AIChatSerializer
    def get_queryset(self):
        emp=employee_for(self.request.user)
        return AIChat.objects.filter(employee=emp,employee__company=company_for(self.request.user)).order_by('-created_at') if emp and company_for(self.request.user) else AIChat.objects.none()
@api_view(['GET'])
def global_search(request):
    term=request.query_params.get('q','').strip()
    if len(term)<2:return Response({'employees':[]})
    company=company_for(request.user)
    if not company:return Response({'employees':[]})
    qs=Employee.objects.select_related('department').filter(company=company)
    if not admin_only(request.user):qs=qs.filter(user=request.user)
    qs=qs.filter(Q(first_name__icontains=term)|Q(last_name__icontains=term)|Q(code__icontains=term)|Q(department__name__icontains=term))[:12]
    return Response({'employees':[{'id':e.id,'name':str(e),'code':e.code,'department':e.department.name if e.department else ''} for e in qs]})
@api_view(['GET'])
def export_report(request):
    if not admin_only(request.user):return Response(status=403)
    company=company_for(request.user)
    if not company:return Response({'detail':'This account is not assigned to a company.'},status=403)
    report=request.query_params.get('type','payroll'); fmt=request.query_params.get('format','xlsx')
    if report=='attendance': rows=Attendance.objects.select_related('employee').all(); headers=['Employee code','Employee','Date','Check in','Check out','Hours','Status','Late minutes']
    elif report=='leave': rows=LeaveRequest.objects.select_related('employee').all(); headers=['Employee code','Employee','Type','From','To','Days','Status','Reason']
    else: rows=Payroll.objects.select_related('employee').all(); headers=['Employee code','Employee','Month','Year','Gross','Deductions','Net','Status']
    rows=rows.filter(employee__company=company)
    if request.query_params.get('employee'):rows=rows.filter(employee_id=request.query_params['employee'])
    if request.query_params.get('department'):rows=rows.filter(employee__department_id=request.query_params['department'])
    start=request.query_params.get('from'); end=request.query_params.get('to')
    if report=='attendance':
        if start:rows=rows.filter(date__gte=start)
        if end:rows=rows.filter(date__lte=end)
        values=lambda r:[r.employee.code,str(r.employee),r.date,r.check_in,r.check_out,r.total_hours,r.status,r.late_minutes]
    elif report=='leave':
        if start:rows=rows.filter(start_date__gte=start)
        if end:rows=rows.filter(end_date__lte=end)
        values=lambda r:[r.employee.code,str(r.employee),r.leave_type,r.start_date,r.end_date,r.total_days,r.status,r.reason]
    else:
        if start:
            y,m=map(int,start[:7].split('-')); rows=rows.filter(Q(year__gt=y)|Q(year=y,month__gte=m))
        if end:
            y,m=map(int,end[:7].split('-')); rows=rows.filter(Q(year__lt=y)|Q(year=y,month__lte=m))
        values=lambda r:[r.employee.code,str(r.employee),r.month,r.year,r.gross,r.deductions,r.net,r.status]
    rows=rows.order_by('-id')
    if fmt=='csv':
        response=HttpResponse(content_type='text/csv');response['Content-Disposition']=f'attachment; filename="epms-{report}.csv"';w=csv.writer(response);w.writerow(headers)
        for r in rows:w.writerow(values(r))
        return response
    if fmt=='pdf':
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.platypus import SimpleDocTemplate,Table,TableStyle
        from reportlab.lib import colors
        buff=io.BytesIO();doc=SimpleDocTemplate(buff,pagesize=landscape(letter)); data=[headers]+[[str(x) for x in values(r)] for r in rows];t=Table(data,repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#8175da')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),8)]));doc.build([t]);response=HttpResponse(buff.getvalue(),content_type='application/pdf');response['Content-Disposition']=f'attachment; filename="epms-{report}.pdf"';return response
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.title=report.title();ws.append(headers)
    for r in rows:ws.append([str(x) if x is not None else '' for x in values(r)])
    buff=io.BytesIO();wb.save(buff);response=HttpResponse(buff.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');response['Content-Disposition']=f'attachment; filename="epms-{report}.xlsx"';return response
@api_view(['GET'])
def bulk_payslips(request):
    if not admin_only(request.user):return Response(status=403)
    company=company_for(request.user)
    if not company:return Response({'detail':'This account is not assigned to a company.'},status=403)
    month=int(request.query_params.get('month',timezone.localdate().month));year=int(request.query_params.get('year',timezone.localdate().year));pays=Payroll.objects.filter(employee__company=company,month=month,year=year,status='Finalized').select_related('employee')
    if request.query_params.get('employee'):pays=pays.filter(employee_id=request.query_params['employee'])
    buff=io.BytesIO();archive=zipfile.ZipFile(buff,'w',zipfile.ZIP_DEFLATED)
    for p in pays:
        pdf=payslip(request,p.pk)
        archive.writestr(f'{p.employee.code}-{year}-{month:02d}.pdf',pdf.content)
    archive.close();response=HttpResponse(buff.getvalue(),content_type='application/zip');response['Content-Disposition']=f'attachment; filename="payslips-{year}-{month:02d}.zip"';return response
@api_view(['POST'])
@permission_classes([AllowAny])
def request_otp(request):
    email=request.data.get('email','').strip().lower();user=User.objects.filter(email__iexact=email,is_active=True).first()
    # Keep responses generic so account existence is not disclosed.
    if user:
        recent=PasswordOTP.objects.filter(user=user,created_at__gte=timezone.now()-timedelta(minutes=1)).exists()
        if not recent:
            code=f'{secrets.randbelow(1000000):06d}';PasswordOTP.objects.create(user=user,otp_hash=make_password(code),expires_at=timezone.now()+timedelta(minutes=10))
            send_mail('EPMS password reset code',f'Your one-time code is {code}. It expires in 10 minutes.',None,[user.email],fail_silently=True)
    return Response({'detail':'If that account exists, a reset code has been sent.'})
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    email=request.data.get('email','').strip().lower();code=request.data.get('otp','');password=request.data.get('new_password','');user=User.objects.filter(email__iexact=email,is_active=True).first()
    if not user or len(password)<8:return Response({'detail':'The code or password is invalid.'},status=400)
    otp=PasswordOTP.objects.filter(user=user,used=False,expires_at__gt=timezone.now()).order_by('-id').first()
    if not otp or not check_password(code,otp.otp_hash):return Response({'detail':'The code or password is invalid.'},status=400)
    user.set_password(password);user.save(update_fields=['password']);otp.used=True;otp.save(update_fields=['used']);PasswordOTP.objects.filter(user=user).exclude(pk=otp.pk).update(used=True);audit(request,'Password reset completed','Authentication');return Response({'detail':'Password updated. You can now sign in.'})
