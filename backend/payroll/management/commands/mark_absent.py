from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from payroll.models import Employee,Attendance,Holiday,ShiftAssignment,WFHRequest,LeaveRequest
class Command(BaseCommand):
    help='Mark scheduled employees absent after their assigned shift ends.'
    def handle(self,*args,**options):
        today=timezone.localdate();now=timezone.localtime().time()
        if today.weekday()>=5 or Holiday.objects.filter(date=today).exists():
            self.stdout.write('No scheduled workday today.');return
        marked=0
        for employee in Employee.objects.filter(status='Active'):
            if Attendance.objects.filter(employee=employee,date=today).exists():continue
            if LeaveRequest.objects.filter(employee=employee,status='Approved',start_date__lte=today,end_date__gte=today).exists():
                Attendance.objects.create(employee=employee,date=today,status='On Leave');continue
            if WFHRequest.objects.filter(employee=employee,status='Approved',start_date__lte=today,end_date__gte=today).exists():
                Attendance.objects.create(employee=employee,date=today,status='WFH');continue
            assignment=ShiftAssignment.objects.filter(employee=employee,effective_from__lte=today).select_related('shift').order_by('-effective_from').first()
            shift_end=assignment.shift.end_time if assignment else datetime.strptime('17:00','%H:%M').time()
            if now>=shift_end:
                Attendance.objects.create(employee=employee,date=today,status='Absent');marked+=1
        self.stdout.write(f'Marked {marked} employee(s) absent for {today}.')
