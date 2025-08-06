"""
Background scheduler for automated notifications and system tasks
"""
import schedule
import time
import threading
import logging
from datetime import datetime
from services.notification_helpers import check_and_alert_low_stock, send_system_alert

logger = logging.getLogger(__name__)

class NotificationScheduler:
    def __init__(self):
        self.scheduler = schedule
        self.running = False
        self.thread = None
    
    def setup_jobs(self):
        """Setup scheduled notification jobs"""
        # Check for low stock every hour during business hours (8 AM - 6 PM)
        for hour in range(8, 19):
            self.scheduler.every().day.at(f"{hour:02d}:00").do(self.check_low_stock_job)
        
        # Daily system health check at 9 AM
        self.scheduler.every().day.at("09:00").do(self.daily_health_check)
        
        # Weekly notification summary on Monday at 8 AM
        self.scheduler.every().monday.at("08:00").do(self.weekly_summary)
        
        logger.info("Notification scheduler jobs configured")
    
    def check_low_stock_job(self):
        """Scheduled job to check for low stock items"""
        try:
            from app import app
            with app.app_context():
                alerts_sent = check_and_alert_low_stock()
                if alerts_sent > 0:
                    logger.info(f"Low stock check completed - {alerts_sent} alerts sent")
        except Exception as e:
            logger.error(f"Error in low stock check job: {e}")
    
    def daily_health_check(self):
        """Daily system health check"""
        try:
            from app import app
            with app.app_context():
                from models import NotificationLog, Item, PurchaseOrder, SalesOrder
                from datetime import datetime, timedelta
                
                # Check notification health
                yesterday = datetime.utcnow() - timedelta(days=1)
                failed_notifications = NotificationLog.query.filter(
                    NotificationLog.sent_at >= yesterday,
                    NotificationLog.success == False
                ).count()
                
                if failed_notifications > 10:  # Threshold for concern
                    send_system_alert(
                        "High Notification Failure Rate",
                        f"{failed_notifications} notifications failed in the last 24 hours. Please check notification settings.",
                        'system_alert'
                    )
            
                # Check for items with zero stock
                zero_stock_items = Item.query.filter(Item.current_stock <= 0).count()
                if zero_stock_items > 0:
                    send_system_alert(
                        "Zero Stock Alert",
                        f"{zero_stock_items} items are currently out of stock. Immediate attention required.",
                        'system_alert'
                    )
                
                logger.info("Daily health check completed")
            
        except Exception as e:
            logger.error(f"Error in daily health check: {e}")
    
    def weekly_summary(self):
        """Weekly notification summary"""
        try:
            from models import NotificationLog, Item
            from datetime import datetime, timedelta
            
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # Get weekly statistics
            total_notifications = NotificationLog.query.filter(
                NotificationLog.sent_at >= week_ago
            ).count()
            
            successful_notifications = NotificationLog.query.filter(
                NotificationLog.sent_at >= week_ago,
                NotificationLog.success == True
            ).count()
            
            low_stock_items = Item.query.filter(
                Item.current_stock <= Item.minimum_stock,
                Item.minimum_stock > 0
            ).count()
            
            summary = f"""Weekly Factory Management Summary:
            
📊 Notification Statistics:
- Total notifications sent: {total_notifications}
- Successful delivery rate: {(successful_notifications/total_notifications*100):.1f}% if total_notifications > 0 else 0
- Items requiring attention: {low_stock_items}

📈 System Health: {'Good' if successful_notifications/total_notifications > 0.9 else 'Needs Attention' if total_notifications > 0 else 'No Activity'}

This is an automated weekly summary from your Factory Management System."""
            
            send_system_alert(
                "Weekly Factory Management Summary",
                summary,
                'system_alert'
            )
            
            logger.info("Weekly summary sent")
            
        except Exception as e:
            logger.error(f"Error in weekly summary: {e}")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            return
        
        self.setup_jobs()
        self.running = True
        
        def run_scheduler():
            while self.running:
                self.scheduler.run_pending()
                time.sleep(60)  # Check every minute
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
        logger.info("Notification scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Notification scheduler stopped")
    
    def get_next_jobs(self):
        """Get information about next scheduled jobs"""
        jobs = []
        for job in self.scheduler.jobs:
            jobs.append({
                'function': job.job_func.__name__,
                'next_run': job.next_run,
                'interval': str(job.interval),
                'unit': job.unit
            })
        return jobs

# Global scheduler instance
notification_scheduler = NotificationScheduler()

# CLI command to start scheduler manually
def start_scheduler():
    """Start the notification scheduler"""
    notification_scheduler.start()
    return "Notification scheduler started"

def stop_scheduler():
    """Stop the notification scheduler"""
    notification_scheduler.stop()
    return "Notification scheduler stopped"