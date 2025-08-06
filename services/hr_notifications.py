"""
HR Notifications Service
Handles all HR-related notifications including salary, advances, employee management, etc.
"""
from datetime import datetime, timedelta
from app import db
from models.notifications import NotificationSettings, NotificationRecipient, NotificationLog
from services.notification_helpers import send_email_notification, send_sms_notification, send_whatsapp_notification

class HRNotificationService:
    """Comprehensive HR notification service"""
    
    @staticmethod
    def notify_salary_payment(employee_id, employee_name, salary_amount, month_year, payment_date, recipients=None):
        """Notify about salary payment"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.salary_payment_notifications:
            return False
        
        subject = f"Salary Payment Processed - {employee_name}"
        message = f"""
        Salary payment has been processed successfully.
        
        Employee: {employee_name} (ID: {employee_id})
        Amount: ₹{salary_amount:,.2f}
        Period: {month_year}
        Payment Date: {payment_date.strftime('%d-%m-%Y')}
        
        This is an automated notification from the Factory Management System.
        """
        
        return HRNotificationService._send_hr_notification(
            'salary_payment', subject, message, recipients, 
            event_id=employee_id, event_data={'amount': salary_amount, 'period': month_year}
        )
    
    @staticmethod
    def notify_advance_payment(employee_id, employee_name, advance_amount, reason, payment_date, recipients=None):
        """Notify about advance payment"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.advance_payment_notifications:
            return False
        
        subject = f"Advance Payment Processed - {employee_name}"
        message = f"""
        Advance payment has been processed.
        
        Employee: {employee_name} (ID: {employee_id})
        Amount: ₹{advance_amount:,.2f}
        Reason: {reason}
        Payment Date: {payment_date.strftime('%d-%m-%Y')}
        
        This advance will be adjusted in future salary payments.
        """
        
        return HRNotificationService._send_hr_notification(
            'advance_payment', subject, message, recipients,
            event_id=employee_id, event_data={'amount': advance_amount, 'reason': reason}
        )
    
    @staticmethod
    def notify_employee_joining(employee_id, employee_name, designation, department, joining_date, recipients=None):
        """Notify about new employee joining"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.employee_joining_notifications:
            return False
        
        subject = f"New Employee Joined - {employee_name}"
        message = f"""
        A new employee has joined the organization.
        
        Employee: {employee_name} (ID: {employee_id})
        Designation: {designation}
        Department: {department}
        Joining Date: {joining_date.strftime('%d-%m-%Y')}
        
        Please ensure proper onboarding and system access setup.
        """
        
        return HRNotificationService._send_hr_notification(
            'employee_joining', subject, message, recipients,
            event_id=employee_id, event_data={'designation': designation, 'department': department}
        )
    
    @staticmethod
    def notify_employee_leaving(employee_id, employee_name, last_working_day, reason, recipients=None):
        """Notify about employee leaving"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.employee_leaving_notifications:
            return False
        
        subject = f"Employee Leaving - {employee_name}"
        message = f"""
        An employee is leaving the organization.
        
        Employee: {employee_name} (ID: {employee_id})
        Last Working Day: {last_working_day.strftime('%d-%m-%Y')}
        Reason: {reason}
        
        Please ensure proper exit formalities and asset handover.
        """
        
        return HRNotificationService._send_hr_notification(
            'employee_leaving', subject, message, recipients,
            event_id=employee_id, event_data={'last_date': last_working_day.isoformat(), 'reason': reason}
        )
    
    @staticmethod
    def notify_attendance_alert(employee_id, employee_name, alert_type, details, recipients=None):
        """Notify about attendance issues"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.attendance_notifications:
            return False
        
        subject = f"Attendance Alert - {employee_name}"
        message = f"""
        Attendance alert for employee.
        
        Employee: {employee_name} (ID: {employee_id})
        Alert Type: {alert_type}
        Details: {details}
        Date: {datetime.now().strftime('%d-%m-%Y')}
        
        Please review and take necessary action.
        """
        
        return HRNotificationService._send_hr_notification(
            'attendance_alert', subject, message, recipients,
            event_id=employee_id, event_data={'alert_type': alert_type, 'details': details}
        )
    
    @staticmethod
    def notify_leave_application(employee_id, employee_name, leave_type, from_date, to_date, days, reason, recipients=None):
        """Notify about leave application"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.leave_application_notifications:
            return False
        
        subject = f"Leave Application - {employee_name}"
        message = f"""
        New leave application submitted.
        
        Employee: {employee_name} (ID: {employee_id})
        Leave Type: {leave_type}
        From: {from_date.strftime('%d-%m-%Y')}
        To: {to_date.strftime('%d-%m-%Y')}
        Days: {days}
        Reason: {reason}
        
        Please review and approve/reject the application.
        """
        
        return HRNotificationService._send_hr_notification(
            'leave_application', subject, message, recipients,
            event_id=employee_id, event_data={
                'leave_type': leave_type, 'days': days, 
                'from_date': from_date.isoformat(), 'to_date': to_date.isoformat()
            }
        )
    
    @staticmethod
    def notify_performance_review(employee_id, employee_name, review_period, reviewer, rating, recipients=None):
        """Notify about performance review completion"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.performance_review_notifications:
            return False
        
        subject = f"Performance Review Completed - {employee_name}"
        message = f"""
        Performance review has been completed.
        
        Employee: {employee_name} (ID: {employee_id})
        Review Period: {review_period}
        Reviewer: {reviewer}
        Rating: {rating}
        Date: {datetime.now().strftime('%d-%m-%Y')}
        
        Review details are available in the HR system.
        """
        
        return HRNotificationService._send_hr_notification(
            'performance_review', subject, message, recipients,
            event_id=employee_id, event_data={'period': review_period, 'reviewer': reviewer, 'rating': rating}
        )
    
    @staticmethod
    def notify_overtime_approval(employee_id, employee_name, overtime_hours, date, reason, approved_by, recipients=None):
        """Notify about overtime approval"""
        settings = NotificationSettings.get_settings()
        
        if not settings.hr_notifications or not settings.overtime_notifications:
            return False
        
        subject = f"Overtime Approved - {employee_name}"
        message = f"""
        Overtime has been approved.
        
        Employee: {employee_name} (ID: {employee_id})
        Hours: {overtime_hours}
        Date: {date.strftime('%d-%m-%Y')}
        Reason: {reason}
        Approved By: {approved_by}
        
        Overtime will be processed in the next payroll.
        """
        
        return HRNotificationService._send_hr_notification(
            'overtime_approval', subject, message, recipients,
            event_id=employee_id, event_data={
                'hours': overtime_hours, 'date': date.isoformat(), 
                'reason': reason, 'approved_by': approved_by
            }
        )
    
    @staticmethod
    def _send_hr_notification(event_type, subject, message, recipients=None, event_id=None, event_data=None):
        """Send HR notification to appropriate recipients"""
        try:
            # Get HR event recipients if not specified
            if recipients is None:
                recipients = NotificationRecipient.query.filter(
                    NotificationRecipient.hr_events == True,
                    NotificationRecipient.is_active == True
                ).all()
            
            if not recipients:
                print(f"No HR notification recipients found for {event_type}")
                return False
            
            success_count = 0
            total_count = 0
            
            for recipient in recipients:
                notification_types = recipient.notification_types.split(',') if recipient.notification_types else []
                
                for notification_type in notification_types:
                    total_count += 1
                    success = False
                    
                    try:
                        if notification_type == 'email' and recipient.email:
                            success = send_email_notification(recipient.email, subject, message)
                        elif notification_type == 'sms' and recipient.phone:
                            success = send_sms_notification(recipient.phone, f"{subject}: {message[:100]}...")
                        elif notification_type == 'whatsapp' and recipient.phone:
                            success = send_whatsapp_notification(recipient.phone, f"{subject}: {message}")
                        elif notification_type == 'in_app':
                            # Create in-app notification (implement as needed)
                            success = True
                        
                        # Log the notification
                        log_entry = NotificationLog(
                            type=notification_type,
                            recipient=recipient.email or recipient.phone or recipient.name,
                            subject=subject,
                            message=message,
                            success=success,
                            event_type=event_type,
                            event_id=event_id,
                            module='hr',
                            response=f"HR notification sent to {recipient.name}" if success else "Failed to send"
                        )
                        db.session.add(log_entry)
                        
                        if success:
                            success_count += 1
                            
                    except Exception as e:
                        print(f"Error sending {notification_type} to {recipient.name}: {str(e)}")
                        
                        # Log the error
                        log_entry = NotificationLog(
                            type=notification_type,
                            recipient=recipient.email or recipient.phone or recipient.name,
                            subject=subject,
                            message=message,
                            success=False,
                            event_type=event_type,
                            event_id=event_id,
                            module='hr',
                            error_message=str(e)
                        )
                        db.session.add(log_entry)
            
            db.session.commit()
            
            print(f"HR notification '{event_type}': {success_count}/{total_count} sent successfully")
            return success_count > 0
            
        except Exception as e:
            db.session.rollback()
            print(f"Error in HR notification service: {str(e)}")
            return False

# Convenience function for quick HR notifications
def send_hr_notification(event_type, **kwargs):
    """Convenient wrapper for sending HR notifications"""
    service = HRNotificationService()
    
    notification_methods = {
        'salary_payment': service.notify_salary_payment,
        'advance_payment': service.notify_advance_payment,
        'employee_joining': service.notify_employee_joining,
        'employee_leaving': service.notify_employee_leaving,
        'attendance_alert': service.notify_attendance_alert,
        'leave_application': service.notify_leave_application,
        'performance_review': service.notify_performance_review,
        'overtime_approval': service.notify_overtime_approval,
    }
    
    if event_type in notification_methods:
        return notification_methods[event_type](**kwargs)
    else:
        print(f"Unknown HR notification type: {event_type}")
        return False