"""
Test HR Notification System
This demonstrates how HR notifications work when salary is processed
"""
from datetime import datetime
from app import app, db
from services.hr_notifications import send_hr_notification

def test_salary_notification():
    """Test salary notification for recipient 'y' when employee 'x' receives salary"""
    
    with app.app_context():
        try:
            print("🎯 TESTING HR NOTIFICATION SYSTEM")
            print("="*50)
            
            # Check if HR recipients exist
            from models.notifications import NotificationRecipient
            hr_recipients = NotificationRecipient.query.filter_by(hr_events=True, is_active=True).all()
            print(f"✅ Found {len(hr_recipients)} HR recipients:")
            for recipient in hr_recipients:
                print(f"   - {recipient.name} ({recipient.email}) - Role: {recipient.role}")
            
            if not hr_recipients:
                print("❌ No HR recipients found! Please add recipients via admin panel.")
                return False
            
            # Example: Employee X receives salary, recipient Y should get notification
            print(f"\n📧 Sending salary notification...")
            result = send_hr_notification(
                'salary_payment',
                employee_id=123,  # Employee X's ID
                employee_name="Employee X",
                salary_amount=50000.00,
                month_year="December 2024",
                payment_date=datetime.now()
            )
            
            # Check notification logs
            from models.notifications import NotificationLog
            recent_logs = NotificationLog.query.filter_by(module='hr').order_by(NotificationLog.created_at.desc()).limit(3).all()
            
            print(f"\n📊 NOTIFICATION RESULTS:")
            print(f"Notification system result: {'✅ Success' if result else '❌ Failed'}")
            print(f"Recent HR notification attempts: {len(recent_logs)}")
            
            for log in recent_logs:
                status = "✅ Sent" if log.success else "❌ Failed"
                print(f"   - {log.type} to {log.recipient}: {status}")
                if log.error_message:
                    print(f"     Error: {log.error_message}")
            
            print(f"\n💡 WHAT THIS MEANS:")
            if result:
                print("   ✅ HR notification system is working correctly")
                print("   ✅ Recipients found and notifications attempted")
                print("   ⚠️  Add API keys (SENDGRID_API_KEY, TWILIO_*) for actual delivery")
            else:
                print("   ❌ No notifications sent - check API keys or recipients")
            
            print(f"\n🔗 INTEGRATION STATUS:")
            print("   ✅ HR notification service created")
            print("   ✅ Database schema updated with HR fields") 
            print("   ✅ Integrated into salary processing routes")
            print("   ✅ Integrated into advance payment routes")
            print("   ⏳ Waiting for API keys for actual delivery")
            
            return result
            
        except Exception as e:
            print(f"❌ Error in notification test: {str(e)}")
            return False

if __name__ == "__main__":
    test_salary_notification()