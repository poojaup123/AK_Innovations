"""
Rectpack Integration for Manufacturing Optimization

This module provides rectangle packing algorithms for various manufacturing scenarios:
1. Material cutting optimization (sheet metal, wood, glass)
2. Production layout planning
3. Inventory space optimization
4. Shipping container optimization
"""

from rectpack import newPacker
import rectpack.guillotine as guillotine
import rectpack.skyline as skyline
import rectpack.maxrects as maxrects
from typing import List, Tuple, Dict, Optional
import json
from datetime import datetime


class MaterialOptimizer:
    """Optimize material cutting patterns for manufacturing"""
    
    def __init__(self, algorithm='skyline'):
        """
        Initialize with different packing algorithms:
        - 'skyline': Good balance of speed and quality (default)
        - 'maxrects': Best packing quality, slower
        - 'guillotine': Fastest, good for large-scale
        """
        self.algorithm = algorithm
        self.packer = self._create_packer()
        
    def _create_packer(self):
        """Create packer with specified algorithm"""
        if self.algorithm == 'maxrects':
            return newPacker(pack_algo=maxrects.MaxRectsBl)
        elif self.algorithm == 'guillotine':
            return newPacker(pack_algo=guillotine.GuillotineBssfSas)
        else:  # skyline (default)
            return newPacker(pack_algo=skyline.SkylineBl)
    
    def optimize_sheet_cutting(self, parts: List[Dict], sheet_dimensions: Tuple[float, float], 
                              max_sheets: int = 10) -> Dict:
        """
        Optimize cutting pattern for sheet materials
        
        Args:
            parts: List of parts with dimensions [{'width': w, 'height': h, 'item_name': name, 'quantity': qty}]
            sheet_dimensions: (width, height) of available sheets
            max_sheets: Maximum number of sheets to use
            
        Returns:
            Optimization results with layout and efficiency metrics
        """
        self.packer = self._create_packer()
        
        # Expand parts by quantity and add to packer
        expanded_parts = []
        for part in parts:
            for i in range(part.get('quantity', 1)):
                expanded_parts.append({
                    'width': part['width'],
                    'height': part['height'],
                    'item_name': part['item_name'],
                    'instance': i + 1
                })
                self.packer.add_rect(part['width'], part['height'])
        
        # Add sheets
        sheet_width, sheet_height = sheet_dimensions
        for i in range(max_sheets):
            self.packer.add_bin(sheet_width, sheet_height)
        
        # Execute packing
        self.packer.pack()
        
        # Calculate metrics
        total_part_area = sum(p['width'] * p['height'] for p in expanded_parts)
        sheets_used = len([bin for bin in self.packer if bin])
        total_sheet_area = sheets_used * sheet_width * sheet_height
        efficiency = (total_part_area / total_sheet_area * 100) if total_sheet_area > 0 else 0
        waste_area = total_sheet_area - total_part_area
        
        # Build layout results
        layouts = []
        part_index = 0
        
        for bin_idx, bin_container in enumerate(self.packer):
            if not bin_container:
                continue
                
            sheet_layout = {
                'sheet_number': bin_idx + 1,
                'sheet_dimensions': {'width': sheet_width, 'height': sheet_height},
                'parts': []
            }
            
            for rect in bin_container:
                if part_index < len(expanded_parts):
                    part_info = expanded_parts[part_index]
                    sheet_layout['parts'].append({
                        'item_name': part_info['item_name'],
                        'instance': part_info['instance'],
                        'dimensions': {'width': rect.width, 'height': rect.height},
                        'position': {'x': rect.x, 'y': rect.y},
                        'rotated': rect.width != part_info['width']  # Simple rotation detection
                    })
                    part_index += 1
            
            layouts.append(sheet_layout)
        
        return {
            'success': len([p for p in expanded_parts]) == part_index,
            'sheets_used': sheets_used,
            'efficiency_percentage': round(efficiency, 2),
            'total_part_area': total_part_area,
            'total_sheet_area': total_sheet_area,
            'waste_area': waste_area,
            'cost_per_sheet': 0,  # To be set externally
            'total_material_cost': 0,  # To be calculated externally
            'layouts': layouts,
            'unpacked_parts': len(expanded_parts) - part_index,
            'algorithm_used': self.algorithm
        }


class ProductionLayoutOptimizer:
    """Optimize production floor layout and inventory arrangement"""
    
    @staticmethod
    def optimize_inventory_layout(items: List[Dict], storage_dimensions: Tuple[float, float]) -> Dict:
        """
        Optimize inventory storage layout
        
        Args:
            items: List of inventory items with dimensions and quantities
            storage_dimensions: (width, height) of storage area
            
        Returns:
            Layout optimization results
        """
        packer = newPacker()
        
        # Add items based on quantities (treating each as a rectangle)
        expanded_items = []
        for item in items:
            # Use unit dimensions multiplied by quantity as area
            width = item.get('length', 1) * item.get('width', 1)
            height = item.get('height', 1)
            quantity = item.get('current_stock', 1)
            
            # Create rectangles for storage optimization
            if quantity > 0:
                # Calculate optimal rectangle dimensions for stacking
                stack_width = min(width, storage_dimensions[0] / 2)
                stack_height = height * min(quantity, 10)  # Limit stack height
                
                packer.add_rect(stack_width, stack_height)
                expanded_items.append({
                    'item_name': item.get('name', 'Unknown'),
                    'item_code': item.get('code', ''),
                    'dimensions': {'width': stack_width, 'height': stack_height},
                    'quantity': quantity
                })
        
        # Add storage area
        packer.add_bin(*storage_dimensions)
        packer.pack()
        
        # Calculate results
        if packer and len(packer) > 0:
            bin_container = next(iter(packer))
            layout_items = []
            
            for i, rect in enumerate(bin_container):
                if i < len(expanded_items):
                    item_info = expanded_items[i]
                    layout_items.append({
                        'item_name': item_info['item_name'],
                        'item_code': item_info['item_code'],
                        'position': {'x': rect.x, 'y': rect.y},
                        'dimensions': {'width': rect.width, 'height': rect.height},
                        'quantity': item_info['quantity']
                    })
            
            total_area_used = sum(rect.width * rect.height for rect in bin_container)
            total_storage_area = storage_dimensions[0] * storage_dimensions[1]
            utilization = (total_area_used / total_storage_area * 100) if total_storage_area > 0 else 0
            
            return {
                'success': True,
                'utilization_percentage': round(utilization, 2),
                'items_placed': len(layout_items),
                'items_total': len(expanded_items),
                'storage_dimensions': {'width': storage_dimensions[0], 'height': storage_dimensions[1]},
                'layout': layout_items
            }
        
        return {'success': False, 'error': 'No items could be placed'}


class PackingCalculator:
    """Utility functions for packing calculations and reports"""
    
    @staticmethod
    def calculate_material_savings(original_sheets: int, optimized_sheets: int, cost_per_sheet: float) -> Dict:
        """Calculate cost savings from optimization"""
        sheets_saved = max(0, original_sheets - optimized_sheets)
        cost_savings = sheets_saved * cost_per_sheet
        percentage_savings = (sheets_saved / original_sheets * 100) if original_sheets > 0 else 0
        
        return {
            'sheets_saved': sheets_saved,
            'cost_savings': cost_savings,
            'percentage_savings': round(percentage_savings, 2),
            'original_sheets': original_sheets,
            'optimized_sheets': optimized_sheets
        }
    
    @staticmethod
    def generate_cutting_report(optimization_result: Dict) -> str:
        """Generate human-readable cutting report"""
        if not optimization_result.get('success'):
            return "Optimization failed - not all parts could be packed"
        
        report = f"""
MATERIAL CUTTING OPTIMIZATION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
- Sheets Required: {optimization_result['sheets_used']}
- Material Efficiency: {optimization_result['efficiency_percentage']}%
- Algorithm Used: {optimization_result['algorithm_used'].title()}
- Unpacked Parts: {optimization_result['unpacked_parts']}

MATERIAL USAGE:
- Total Part Area: {optimization_result['total_part_area']:.2f} sq units
- Total Sheet Area: {optimization_result['total_sheet_area']:.2f} sq units
- Waste Area: {optimization_result['waste_area']:.2f} sq units

CUTTING LAYOUTS:
"""
        
        for layout in optimization_result['layouts']:
            report += f"\nSheet {layout['sheet_number']} ({layout['sheet_dimensions']['width']}x{layout['sheet_dimensions']['height']}):\n"
            for part in layout['parts']:
                rotation_note = " (rotated)" if part['rotated'] else ""
                report += f"  - {part['item_name']} #{part['instance']}: "
                report += f"{part['dimensions']['width']}x{part['dimensions']['height']} "
                report += f"at ({part['position']['x']}, {part['position']['y']}){rotation_note}\n"
        
        return report
    
    @staticmethod
    def export_to_json(optimization_result: Dict, filename: str = None) -> str:
        """Export optimization results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"cutting_optimization_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(optimization_result, f, indent=2, default=str)
        
        return filename


def demo_material_optimization():
    """Demo function showing Rectpack integration"""
    # Example parts list (from BOM or production orders)
    parts = [
        {'width': 100, 'height': 50, 'item_name': 'Bracket', 'quantity': 8},
        {'width': 75, 'height': 75, 'item_name': 'Base Plate', 'quantity': 4},
        {'width': 50, 'height': 30, 'item_name': 'Small Component', 'quantity': 12},
        {'width': 150, 'height': 80, 'item_name': 'Main Panel', 'quantity': 2},
    ]
    
    # Standard sheet size (e.g., 4x8 feet = 48x96 inches)
    sheet_size = (1200, 600)  # mm
    
    # Optimize with different algorithms
    algorithms = ['skyline', 'maxrects', 'guillotine']
    
    print("RECTPACK MATERIAL OPTIMIZATION DEMO")
    print("=" * 50)
    
    for algo in algorithms:
        optimizer = MaterialOptimizer(algorithm=algo)
        result = optimizer.optimize_sheet_cutting(parts, sheet_size)
        
        print(f"\n{algo.upper()} ALGORITHM:")
        print(f"Sheets needed: {result['sheets_used']}")
        print(f"Efficiency: {result['efficiency_percentage']}%")
        print(f"Waste area: {result['waste_area']:.0f} sq mm")
        
        if result['unpacked_parts'] > 0:
            print(f"Warning: {result['unpacked_parts']} parts couldn't be packed!")


if __name__ == "__main__":
    demo_material_optimization()