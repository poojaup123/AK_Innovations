"""
Smart UOM Conversion Intelligence Service
Handles automatic unit conversions across purchase → inventory → job work → GRN workflow
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

class UOMConverter:
    """Intelligent Unit of Measure conversion system"""
    
    # Standard conversion factors (to base units)
    CONVERSION_FACTORS = {
        # Weight conversions (base: kg)
        'kg': 1.0,
        'g': 0.001,
        'ton': 1000.0,
        'lbs': 0.453592,
        'oz': 0.0283495,
        
        # Length conversions (base: m)
        'm': 1.0,
        'cm': 0.01,
        'mm': 0.001,
        'ft': 0.3048,
        'in': 0.0254,
        
        # Volume conversions (base: l)
        'l': 1.0,
        'ml': 0.001,
        'gal': 3.78541,
        
        # Count conversions (base: pcs)
        'pcs': 1.0,
        'nos': 1.0,
        'dozen': 12.0,
        'gross': 144.0,
        
        # Area conversions (base: sqm)
        'sqm': 1.0,
        'sqft': 0.092903,
        'sqcm': 0.0001,
    }
    
    # UOM category mapping
    UOM_CATEGORIES = {
        'weight': ['kg', 'g', 'ton', 'lbs', 'oz'],
        'length': ['m', 'cm', 'mm', 'ft', 'in'],
        'volume': ['l', 'ml', 'gal'],
        'count': ['pcs', 'nos', 'dozen', 'gross'],
        'area': ['sqm', 'sqft', 'sqcm']
    }
    
    @classmethod
    def get_uom_category(cls, uom):
        """Get the category of a UOM"""
        uom_lower = uom.lower()
        for category, uoms in cls.UOM_CATEGORIES.items():
            if uom_lower in uoms:
                return category
        return 'unknown'
    
    @classmethod
    def can_convert(cls, from_uom, to_uom):
        """Check if conversion is possible between two UOMs"""
        from_category = cls.get_uom_category(from_uom)
        to_category = cls.get_uom_category(to_uom)
        return from_category == to_category and from_category != 'unknown'
    
    @classmethod
    def convert_quantity(cls, quantity, from_uom, to_uom, conversion_factor=None):
        """
        Convert quantity from one UOM to another
        
        Args:
            quantity: Original quantity
            from_uom: Source unit of measure
            to_uom: Target unit of measure
            conversion_factor: Custom conversion factor (optional)
        
        Returns:
            Converted quantity or None if conversion not possible
        """
        try:
            quantity = Decimal(str(quantity))
            
            # Use custom conversion factor if provided
            if conversion_factor:
                return float(quantity * Decimal(str(conversion_factor)))
            
            # Check if standard conversion is possible
            if not cls.can_convert(from_uom, to_uom):
                logger.warning(f"Cannot convert from {from_uom} to {to_uom} - different categories")
                return None
            
            from_uom_lower = from_uom.lower()
            to_uom_lower = to_uom.lower()
            
            # Get conversion factors
            from_factor = cls.CONVERSION_FACTORS.get(from_uom_lower)
            to_factor = cls.CONVERSION_FACTORS.get(to_uom_lower)
            
            if from_factor is None or to_factor is None:
                logger.warning(f"Conversion factors not found for {from_uom} or {to_uom}")
                return None
            
            # Convert to base unit, then to target unit
            base_quantity = quantity * Decimal(str(from_factor))
            converted_quantity = base_quantity / Decimal(str(to_factor))
            
            return float(converted_quantity.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
            
        except Exception as e:
            logger.error(f"Error converting {quantity} from {from_uom} to {to_uom}: {e}")
            return None
    
    @classmethod
    def get_conversion_info(cls, from_uom, to_uom, quantity=1):
        """Get conversion information between two UOMs"""
        converted = cls.convert_quantity(quantity, from_uom, to_uom)
        if converted is None:
            return None
        
        return {
            'from_uom': from_uom,
            'to_uom': to_uom,
            'from_quantity': quantity,
            'to_quantity': converted,
            'conversion_rate': converted / quantity if quantity > 0 else 0,
            'can_convert': True
        }
    
    @classmethod
    def auto_convert_for_workflow(cls, item, purchase_uom, purchase_quantity, target_workflow='job_work'):
        """
        Automatically convert quantities for different workflow stages
        
        Args:
            item: Item object with conversion factors
            purchase_uom: Original purchase unit
            purchase_quantity: Original purchase quantity
            target_workflow: Target workflow (job_work, inventory, grn)
        
        Returns:
            Dict with conversion information
        """
        try:
            # Get item's preferred UOM for the target workflow
            inventory_uom = getattr(item, 'unit_of_measure', 'pcs')
            
            # Check if item has custom conversion factor
            custom_factor = getattr(item, 'uom_conversion_factor', None)
            
            # Convert to inventory UOM
            converted_qty = cls.convert_quantity(
                purchase_quantity, 
                purchase_uom, 
                inventory_uom,
                custom_factor
            )
            
            if converted_qty is None:
                # If standard conversion fails, use custom factor if available
                if custom_factor:
                    converted_qty = float(purchase_quantity) * float(custom_factor)
                else:
                    converted_qty = float(purchase_quantity)  # No conversion
            
            return {
                'original_quantity': purchase_quantity,
                'original_uom': purchase_uom,
                'converted_quantity': converted_qty,
                'converted_uom': inventory_uom,
                'conversion_factor': custom_factor,
                'conversion_applied': converted_qty != float(purchase_quantity),
                'workflow': target_workflow
            }
            
        except Exception as e:
            logger.error(f"Error in auto conversion for item {item.id}: {e}")
            return {
                'original_quantity': purchase_quantity,
                'original_uom': purchase_uom,
                'converted_quantity': float(purchase_quantity),
                'converted_uom': purchase_uom,
                'conversion_factor': None,
                'conversion_applied': False,
                'workflow': target_workflow,
                'error': str(e)
            }