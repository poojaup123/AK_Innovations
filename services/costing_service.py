"""Comprehensive Costing Service with Scrap, Overhead, and Wastage tracking"""

from app import db
from models import JobWork, Item
from models.production import ProductionOrder, ProductionProcess
from models.batch import InventoryBatch, BatchMovement
from services.accounting_service import AccountingService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CostingService:
    """Advanced costing system with complete tracking"""
    
    @staticmethod
    def calculate_job_work_cost(job_work_id, include_overhead=True):
        """Calculate comprehensive job work cost"""
        try:
            job_work = JobWork.query.get(job_work_id)
            if not job_work:
                return {'success': False, 'error': 'Job work not found'}
            
            cost_breakdown = {
                'material_cost': 0.0,
                'labor_cost': 0.0,
                'overhead_cost': 0.0,
                'scrap_cost': 0.0,
                'wastage_cost': 0.0,
                'vendor_cost': 0.0,
                'total_cost': 0.0,
                'cost_per_unit': 0.0,
                'efficiency_percentage': 100.0
            }
            
            # 1. Material Cost Calculation
            material_cost = CostingService._calculate_material_cost(job_work)
            cost_breakdown['material_cost'] = material_cost['total_cost']
            cost_breakdown['scrap_cost'] = material_cost['scrap_cost']
            cost_breakdown['wastage_cost'] = material_cost['wastage_cost']
            
            # 2. Labor Cost (for in-house jobs)
            if job_work.work_type == 'in_house':
                labor_cost = CostingService._calculate_labor_cost(job_work)
                cost_breakdown['labor_cost'] = labor_cost['total_cost']
            
            # 3. Vendor Cost (for outsourced jobs)
            if job_work.work_type == 'outsourced':
                vendor_cost = job_work.actual_cost or job_work.estimated_cost or 0
                cost_breakdown['vendor_cost'] = vendor_cost
            
            # 4. Overhead Cost
            if include_overhead:
                overhead_cost = CostingService._calculate_overhead_cost(job_work, cost_breakdown)
                cost_breakdown['overhead_cost'] = overhead_cost
            
            # 5. Calculate totals
            cost_breakdown['total_cost'] = (
                cost_breakdown['material_cost'] +
                cost_breakdown['labor_cost'] +
                cost_breakdown['overhead_cost'] +
                cost_breakdown['vendor_cost'] +
                cost_breakdown['scrap_cost'] +
                cost_breakdown['wastage_cost']
            )
            
            # 6. Cost per unit
            output_qty = job_work.quantity_received or job_work.expected_output or 1
            cost_breakdown['cost_per_unit'] = cost_breakdown['total_cost'] / output_qty if output_qty > 0 else 0
            
            # 7. Efficiency calculation
            if job_work.quantity_to_issue and job_work.quantity_received:
                theoretical_efficiency = (job_work.quantity_received / job_work.quantity_to_issue) * 100
                cost_breakdown['efficiency_percentage'] = min(theoretical_efficiency, 100.0)
            
            # Update job work with calculated costs
            job_work.material_cost = cost_breakdown['material_cost']
            job_work.labor_cost = cost_breakdown['labor_cost']
            job_work.overhead_cost = cost_breakdown['overhead_cost']
            job_work.total_cost = cost_breakdown['total_cost']
            job_work.cost_per_unit = cost_breakdown['cost_per_unit']
            
            db.session.commit()
            
            logger.info(f"Calculated costs for job work {job_work.job_number}: Total={cost_breakdown['total_cost']}")
            
            return {'success': True, 'cost_breakdown': cost_breakdown}
            
        except Exception as e:
            logger.error(f"Error calculating job work cost: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_material_cost(job_work):
        """Calculate detailed material cost with scrap and wastage"""
        try:
            material_data = {
                'raw_material_cost': 0.0,
                'scrap_cost': 0.0,
                'wastage_cost': 0.0,
                'total_cost': 0.0
            }
            
            # Get input material cost from batch
            if job_work.input_material_id:
                input_item = Item.query.get(job_work.input_material_id)
                if input_item:
                    base_cost = (job_work.quantity_to_issue or 0) * (input_item.unit_price or 0)
                    material_data['raw_material_cost'] = base_cost
            
            # Calculate actual scrap cost
            if hasattr(job_work, 'scrap_quantity') and job_work.scrap_quantity:
                scrap_rate = input_item.unit_price if input_item else 0
                material_data['scrap_cost'] = job_work.scrap_quantity * scrap_rate
            
            # Calculate wastage (issued - received - scrap)
            issued_qty = job_work.quantity_to_issue or 0
            received_qty = job_work.quantity_received or 0
            scrap_qty = getattr(job_work, 'scrap_quantity', 0) or 0
            
            wastage_qty = max(0, issued_qty - received_qty - scrap_qty)
            if wastage_qty > 0 and input_item:
                material_data['wastage_cost'] = wastage_qty * (input_item.unit_price or 0)
            
            material_data['total_cost'] = (
                material_data['raw_material_cost'] +
                material_data['scrap_cost'] +
                material_data['wastage_cost']
            )
            
            return material_data
            
        except Exception as e:
            logger.error(f"Error calculating material cost: {str(e)}")
            return {'raw_material_cost': 0.0, 'scrap_cost': 0.0, 'wastage_cost': 0.0, 'total_cost': 0.0}
    
    @staticmethod
    def _calculate_labor_cost(job_work):
        """Calculate labor cost for in-house jobs"""
        try:
            from models import DailyJobWorkEntry
            
            labor_data = {
                'total_hours': 0.0,
                'total_cost': 0.0,
                'average_rate': 0.0
            }
            
            # Get daily entries for this job work
            daily_entries = DailyJobWorkEntry.query.filter_by(job_work_id=job_work.id).all()
            
            total_hours = 0.0
            total_cost = 0.0
            
            for entry in daily_entries:
                hours = entry.hours_worked or 0
                rate = entry.hourly_rate or 0
                
                total_hours += hours
                total_cost += hours * rate
            
            labor_data['total_hours'] = total_hours
            labor_data['total_cost'] = total_cost
            labor_data['average_rate'] = total_cost / total_hours if total_hours > 0 else 0
            
            return labor_data
            
        except Exception as e:
            logger.error(f"Error calculating labor cost: {str(e)}")
            return {'total_hours': 0.0, 'total_cost': 0.0, 'average_rate': 0.0}
    
    @staticmethod
    def _calculate_overhead_cost(job_work, base_costs):
        """Calculate overhead cost based on various factors"""
        try:
            # Get company overhead rates
            overhead_rate = CostingService._get_overhead_rate(job_work.work_type)
            
            # Calculate overhead base (material + labor for in-house, or vendor cost for outsourced)
            if job_work.work_type == 'in_house':
                overhead_base = base_costs['material_cost'] + base_costs['labor_cost']
            else:
                overhead_base = base_costs['vendor_cost']
            
            overhead_cost = overhead_base * (overhead_rate / 100)
            
            return overhead_cost
            
        except Exception as e:
            logger.error(f"Error calculating overhead cost: {str(e)}")
            return 0.0
    
    @staticmethod
    def _get_overhead_rate(work_type):
        """Get overhead rate based on work type"""
        try:
            from models import CompanySettings
            settings = CompanySettings.query.first()
            
            if work_type == 'in_house':
                return settings.inhouse_overhead_rate if settings else 15.0  # Default 15%
            else:
                return settings.outsourced_overhead_rate if settings else 5.0  # Default 5%
                
        except:
            return 15.0 if work_type == 'in_house' else 5.0
    
    @staticmethod
    def calculate_production_order_cost(production_order_id):
        """Calculate complete production order cost"""
        try:
            production_order = ProductionOrder.query.get(production_order_id)
            if not production_order:
                return {'success': False, 'error': 'Production order not found'}
            
            cost_summary = {
                'material_cost': 0.0,
                'job_work_cost': 0.0,
                'labor_cost': 0.0,
                'overhead_cost': 0.0,
                'scrap_cost': 0.0,
                'total_cost': 0.0,
                'cost_per_unit': 0.0,
                'job_work_breakdown': []
            }
            
            # Sum up all job work costs
            for job_work in production_order.job_works:
                jw_cost = CostingService.calculate_job_work_cost(job_work.id)
                if jw_cost['success']:
                    breakdown = jw_cost['cost_breakdown']
                    
                    cost_summary['material_cost'] += breakdown['material_cost']
                    cost_summary['job_work_cost'] += breakdown['vendor_cost']
                    cost_summary['labor_cost'] += breakdown['labor_cost']
                    cost_summary['overhead_cost'] += breakdown['overhead_cost']
                    cost_summary['scrap_cost'] += breakdown['scrap_cost'] + breakdown['wastage_cost']
                    
                    cost_summary['job_work_breakdown'].append({
                        'job_number': job_work.job_number,
                        'work_type': job_work.work_type,
                        'total_cost': breakdown['total_cost'],
                        'cost_per_unit': breakdown['cost_per_unit']
                    })
            
            cost_summary['total_cost'] = (
                cost_summary['material_cost'] +
                cost_summary['job_work_cost'] +
                cost_summary['labor_cost'] +
                cost_summary['overhead_cost'] +
                cost_summary['scrap_cost']
            )
            
            # Cost per unit
            if production_order.quantity_produced > 0:
                cost_summary['cost_per_unit'] = cost_summary['total_cost'] / production_order.quantity_produced
            
            # Update production order
            production_order.material_cost = cost_summary['material_cost']
            production_order.job_work_cost = cost_summary['job_work_cost'] 
            production_order.labor_cost = cost_summary['labor_cost']
            production_order.overhead_cost = cost_summary['overhead_cost']
            production_order.total_cost = cost_summary['total_cost']
            production_order.cost_per_unit = cost_summary['cost_per_unit']
            
            db.session.commit()
            
            return {'success': True, 'cost_summary': cost_summary}
            
        except Exception as e:
            logger.error(f"Error calculating production order cost: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def track_scrap_and_wastage(reference_type, reference_id, scrap_data):
        """Track scrap and wastage with proper costing"""
        try:
            from models import ScrapRecord
            
            scrap_record = ScrapRecord(
                reference_type=reference_type,
                reference_id=reference_id,
                item_id=scrap_data['item_id'],
                scrap_quantity=scrap_data['scrap_quantity'],
                scrap_reason=scrap_data['scrap_reason'],
                wastage_quantity=scrap_data.get('wastage_quantity', 0),
                total_loss_value=scrap_data['total_loss_value'],
                recorded_date=datetime.utcnow().date(),
                recorded_by=scrap_data.get('recorded_by', 1),
                remarks=scrap_data.get('remarks', '')
            )
            
            db.session.add(scrap_record)
            
            # Create accounting entry for scrap loss
            if scrap_data['total_loss_value'] > 0:
                AccountingService.create_job_work_cost_entries(
                    reference_id, 
                    {'scrap': scrap_data['total_loss_value']}
                )
            
            db.session.commit()
            
            return {'success': True, 'scrap_record': scrap_record.to_dict()}
            
        except Exception as e:
            logger.error(f"Error tracking scrap and wastage: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_cost_analysis_report(start_date, end_date, filters=None):
        """Generate comprehensive cost analysis report"""
        try:
            # Get job works in date range
            query = JobWork.query.filter(
                JobWork.created_at >= start_date,
                JobWork.created_at <= end_date
            )
            
            if filters:
                if filters.get('work_type'):
                    query = query.filter(JobWork.work_type == filters['work_type'])
                if filters.get('status'):
                    query = query.filter(JobWork.status == filters['status'])
            
            job_works = query.all()
            
            report_data = {
                'summary': {
                    'total_jobs': len(job_works),
                    'total_cost': 0.0,
                    'average_cost_per_job': 0.0,
                    'total_material_cost': 0.0,
                    'total_labor_cost': 0.0,
                    'total_overhead_cost': 0.0,
                    'total_scrap_cost': 0.0
                },
                'by_work_type': {},
                'efficiency_metrics': {
                    'average_efficiency': 0.0,
                    'material_utilization': 0.0,
                    'scrap_percentage': 0.0
                },
                'top_cost_drivers': [],
                'detailed_breakdown': []
            }
            
            total_efficiency = 0.0
            valid_efficiency_count = 0
            
            for job_work in job_works:
                cost_result = CostingService.calculate_job_work_cost(job_work.id, include_overhead=True)
                if cost_result['success']:
                    breakdown = cost_result['cost_breakdown']
                    
                    # Update summary
                    report_data['summary']['total_cost'] += breakdown['total_cost']
                    report_data['summary']['total_material_cost'] += breakdown['material_cost']
                    report_data['summary']['total_labor_cost'] += breakdown['labor_cost']
                    report_data['summary']['total_overhead_cost'] += breakdown['overhead_cost']
                    report_data['summary']['total_scrap_cost'] += breakdown['scrap_cost'] + breakdown['wastage_cost']
                    
                    # Track by work type
                    work_type = job_work.work_type
                    if work_type not in report_data['by_work_type']:
                        report_data['by_work_type'][work_type] = {
                            'count': 0,
                            'total_cost': 0.0,
                            'average_cost': 0.0
                        }
                    
                    report_data['by_work_type'][work_type]['count'] += 1
                    report_data['by_work_type'][work_type]['total_cost'] += breakdown['total_cost']
                    
                    # Efficiency tracking
                    if breakdown['efficiency_percentage'] > 0:
                        total_efficiency += breakdown['efficiency_percentage']
                        valid_efficiency_count += 1
                    
                    # Add to detailed breakdown
                    report_data['detailed_breakdown'].append({
                        'job_number': job_work.job_number,
                        'work_type': job_work.work_type,
                        'status': job_work.status,
                        'total_cost': breakdown['total_cost'],
                        'cost_per_unit': breakdown['cost_per_unit'],
                        'efficiency': breakdown['efficiency_percentage'],
                        'material_cost': breakdown['material_cost'],
                        'scrap_cost': breakdown['scrap_cost']
                    })
            
            # Calculate averages
            total_jobs = report_data['summary']['total_jobs']
            if total_jobs > 0:
                report_data['summary']['average_cost_per_job'] = report_data['summary']['total_cost'] / total_jobs
            
            for work_type_data in report_data['by_work_type'].values():
                if work_type_data['count'] > 0:
                    work_type_data['average_cost'] = work_type_data['total_cost'] / work_type_data['count']
            
            # Efficiency metrics
            if valid_efficiency_count > 0:
                report_data['efficiency_metrics']['average_efficiency'] = total_efficiency / valid_efficiency_count
            
            if report_data['summary']['total_material_cost'] > 0:
                scrap_percentage = (report_data['summary']['total_scrap_cost'] / report_data['summary']['total_material_cost']) * 100
                report_data['efficiency_metrics']['scrap_percentage'] = scrap_percentage
                report_data['efficiency_metrics']['material_utilization'] = 100 - scrap_percentage
            
            # Top cost drivers (sort by total cost descending)
            report_data['top_cost_drivers'] = sorted(
                report_data['detailed_breakdown'],
                key=lambda x: x['total_cost'],
                reverse=True
            )[:10]
            
            return {'success': True, 'report': report_data}
            
        except Exception as e:
            logger.error(f"Error generating cost analysis report: {str(e)}")
            return {'success': False, 'error': str(e)}